# DAY 05 联调契约

范围：沿用 Vue / FastAPI / SQLite，补齐现有规则模拟链路，不接入模型或真实设备，不重写前四天。品牌天亨，界面使用中文模拟说明。

1. `POST /api/v1/demo-scenarios/evt-008/prepare {}` 显式幂等准备一次场景；GET `/api/v1/demo-scenarios/evt-008` 读取状态，未准备404。不能刷新/启动自动创建或重置。
2. 返回 `{incident_id,incident_code:'EVT-008',device_id:'dev-temp-01',device_code:'TEMP-008',building_id:'loc-training',resource_id:'UAV-003',task_code:'TASK-008',root_task_id:null|string,is_simulated:true}`。保留历史ID。场景为温度30→49→68.5℃、烟雾未触发、摄像机通信在线，均为模拟。
3. 首次该事件有效核查创建无人机任务保存真实 TASK-008；普通分配保留008，允许编号空缺，禁止创建占号任务。若已有无关008冲突明确报错。重复同run/type幂等；后续run/重试使用唯一新code，不重置或伪装多个008。
4. 统一参考规则沿用≥60℃模拟阈值，显示低于60未命中本规则，不宣称真实正常范围。无依据的设备正常范围显示待核实。设备数据、地图、证据使用同一后端references。
5. 设备入口提供analysis-context关联事件列表，用户选择明确事件后创建同一证据快照；source_selection支持设备并后端验证关联。设备无事件提供原因，不能创建无关事件。
6. 新核查基于冻结证据增加温度趋势、同区域证据、风险判断、可能原因、不确定性与建议，明确规则模拟。新报告与结果同事务持久化，旧报告/快照不改写。
7. GET `/runs/{run_id}/assessment-report`、`/assessment-reports/{report_id}`、`/assessment-reports` 提供保存报告；前端查看/JSON下载。旧核查未生成报告明确404，不拿最新观测重算历史。
8. 风险研判和工作台共享当前run/snapshot选择；EVT-008、TEMP-008、TASK-008、UAV-003跨页真实关联。设备抽屉补类型/参考/时间/来源，报告与执行结果可回看。
9. 交互修复：无效缓存导航回退、异步旧设备数据覆盖防护、全屏失败反馈、空态/错误可恢复；现有预留模块明确标识，不假称已实现。
10. 根任务实际浏览器完成16步验收并保存截图，后端自动测试故障/幂等/隔离，前端构建与回归检查。所有测试证据区分实测、自动覆盖和未验收。

分工：后端agent负责backend/**；前端agent负责frontend/**；根负责文档、素材、服务与浏览器验收；审查agent只读。具体报告与reference字段由前后端agent直接对齐并记录最终实现，不得前端猜测硬编码。
