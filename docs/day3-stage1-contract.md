# DAY 03 阶段一：事件上下文与证据快照契约

范围：在保留 Day 1/2 的前提下，补齐事件详情、统一查询证据、支持地图进入证据工作台及持久化恢复。本阶段仍明确为三工具规则核查；真实智谱 Agent 是阶段二验收目标。本阶段不调用模型，不创建执行计划，不自动巡检。

## 数据口径

- event_snapshot：指定事件关联观测；按设备/指标取该事件最新记录用于摘要，保留全部原观测用于追溯。
- current_device_state：当前全库该设备各指标最新记录；与地图当前状态同源。两种口径不得混用，也不得把“当前”包装为真实遥测。
- 证据必须包含原 observation_id/id、incident_id、device_id、observed_at、quality、data_scope。
- 事件关联采用同一后端定义；设备离线/消防事件不能引入同楼层所有设备作为直接证据。
- 同一 snapshot_id 的查询、界面展示和结果引用必须一致。服务重启和后续观测变化不得改变已保存快照。

## 接口（均 /api/v1 前缀）

GET /incidents/{incident_id}/context -> EvidenceContext

EvidenceContext = {
 incident: existing Incident + {source:{kind:string,label:string},building_id:string|null,building_name:string|null,device_ids:string[]},
 data_scope:'event_snapshot',
 devices:EvidenceDevice[], observations:EvidenceObservation[],
 current_devices:EvidenceDevice[], history:Incident[],
 source_context:{source_view:'overview'|'map'|'coordination',image_id:string|null,selection:{kind:'incident',id:string}},
 is_simulated:true
}

EvidenceObservation = existing Observation + {observation_id:string,data_scope:'event_snapshot'|'current_device_state'}
EvidenceDevice = {id,code,name,type,location_id,status,last_seen,is_simulated:true,metrics:EvidenceMetric[]}
EvidenceMetric = {kind,label,value:number|string|null,unit,observation_id,observed_at,incident_id,quality,data_scope}

POST /incidents/{incident_id}/evidence-snapshots {source_view?,image_id?} -> EvidenceSnapshot (201)
EvidenceSnapshot = EvidenceContext + {snapshot_id:string,captured_at:string,checksum:string}
GET /evidence-snapshots/{snapshot_id} -> saved EvidenceSnapshot
快照由后端按当前数据库事务生成并保存，不接受前端提交伪造的观测值或事件内容。source_view 默认 map，image_id 缺省从建筑位置推导，非空且错图时拒绝。无定位建筑允许 null 并显示待核实。

POST /runs 增加可选 evidence_snapshot_id。必须校验 snapshot.incident.id 与请求 incident_id 一致。返回 Run 增加 evidence_snapshot_id:string|null；工具查询使用已保存快照，工具结果增加 evidence_snapshot_id/data_scope/incident_id。结果仍使用原 Day1 RiskResult 并附快照引用。保留旧调用/取消/SSE/历史运行兼容性。

POST /scenarios/temperature-only/trigger -> 新建独立 DEMO 事件，68.5°C、烟雾0、摄像机在线且无摄像机告警。只由用户点击或验收调用创建；不自动seed、不覆盖历史。地图当前读数随新观测变化，旧事件证据保持78°C/烟雾告警。与原 fire/trigger 构成两类对照场景。

## 前端

- 地图事件抽屉显示编号、来源、时间、建筑、等级、状态、关联设备，复用独立 IncidentEvidencePanel。
- 区分事件证据与当前设备状态；按钮“发起研判 · 证据核查”，旁注明阶段一为规则演示、真实模型尚未接入。
- 点击按钮创建快照，打开独立 EvidenceWorkbench（智能工作台内部），显示快照ID/时间/证据，调用实际三项工具，显示日志和规则初评。禁止用计时动画伪造查询进度。
- 保存所选 snapshot_id/run_id 到 localStorage 仅供恢复索引；全部事实来自后端。刷新通过GET恢复；返回地图恢复来源视图/图片/事件。
- 提供明确按钮创建单温异常对照场景，显示忙碌/失败状态，旧数据保留。不新建另一套前端读数。
- 原 Day1 工作台、Day2 map_tasks 与巡检不破坏。

## 验收门槛

事件/设备/观测ID一致；快照和3工具输出一致；当前状态与事件证据明确区分；后续数据变化/服务重启不改变历史快照；未知ID/错事件快照/错图拒绝；两种场景不同结果且温度异常不等于火灾；地图→快照→查询→保存→刷新→返回实际操作；旧测试通过。

后端所有改动由后端实施 agent 负责；前端由前端实施 agent 负责。根 agent 管理契约、审查、运行服务和实际验收，按阶段报告。
