# Day 1 已实现接口

本机 API 文档：http://127.0.0.1:8000/docs。以下业务路径均有 `/api/v1` 前缀。

| 方法 | 路径 | 实际用途 |
|---|---|---|
| GET | /system/status | 当前阶段、已实现能力、脱敏独立模型探测结果 |
| GET | /overview | 事件和设备数量、活动分析任务数量 |
| GET | /incidents、/incidents/{id} | 演示事件列表和详情 |
| POST | /scenarios/fire/trigger | 创建独立模拟场景，保留历史 |
| GET | /locations | 虚构校园与位置 |
| GET | /devices?incident_id= | 按事件观测派生设备状态 |
| GET | /devices/{id}/observations?incident_id= | 查询指定事件的设备读数 |
| GET | /knowledge/search?q=、/knowledge/{id} | 本地预置资料查询与原文 |
| GET | /resources | 模拟人员角色与资源 |
| POST | /conversations | 新建会话 |
| GET | /conversations、/conversations/{id} | 会话列表与已保存消息 |
| POST | /runs | 创建基础核查，返回 202 和 run_id |
| GET | /runs、/runs/{id} | 分析运行与结果 |
| GET | /runs/{id}/events?after= | SSE，支持 Last-Event-ID 补发；事件名 update |
| POST | /runs/{id}/cancel | 阻止后续工具执行，保留已完成记录 |
| GET | /tasks | Day 4 起返回执行任务列表，兼容 /execution-tasks |

`GET /health` 位于此前缀之外，仅返回进程存活状态。

运行输入需要 conversation_id、incident_id、instruction。未知对象返回 404，空白指令返回 422，同一会话已有运行时返回 409。运行阶段与结果落库后再向页面展示，SSE 断开不会自动取消业务。

附件上传、方案审批与正式 PDF 报告 API 尚未开放；基础初评 JSON 下载由浏览器根据已取回的运行与证据记录生成。DAY 05 结构化规则研判报告接口见下文。

## Day 4 执行接口

业务路径仍有 `/api/v1` 前缀。完整结构见 [day4-contract.md](day4-contract.md)。

| 方法 | 路径 | 实际用途 |
|---|---|---|
| GET / POST | /execution-tasks | 列表 / 手动创建模拟执行任务 |
| POST | /execution-tasks/from-run | 从已完成且有证据快照的规则核查创建；相同来源和类型幂等 |
| GET | /execution-tasks/{id} | 状态、步骤、日志、来源与报告 |
| GET | /execution-resources?task_id= | 三类模拟资源及任务适配原因 |
| POST | /execution-tasks/{id}/assign | 保存资源分配，仅待执行允许 |
| POST | /execution-tasks/{id}/start | 原子占用资源并开始模拟执行 |
| POST | /execution-tasks/{id}/cancel | 取消、冻结进度并释放资源 |
| POST | /execution-tasks/{id}/retry | 创建关联子任务，保留原始结果 |
| GET | /execution-tasks/{id}/report | 已完成任务报告，未完成返回 409 |
| GET | /situation | 加入 execution_tasks、execution_resources 供地图共用 |

报告是后端保存的任务专属模拟执行记录，需人工复核，完成后不会自动关闭原风险事件。

## Day 5 联调与规则报告接口

以下路径同样带 `/api/v1` 前缀；报告与证据为已保存快照，不使用新观测重算历史。

| 方法 | 路径 | 实际用途 |
|---|---|---|
| POST | /demo-scenarios/evt-008/prepare | 显式且幂等准备 EVT-008，保留旧任务和历史 |
| GET | /demo-scenarios/evt-008 | 场景对象映射及根任务 ID；未准备返回 404 |
| GET | /devices/{id}/analysis-context?incident_id= | 设备关联事件、所选事件和可分析状态 |
| GET | /runs/{id}/assessment-report | 核查的结构化规则报告；旧核查无报告返回 404 |
| GET | /assessment-reports/{id} | 按报告 ID 查看持久化内容 |
| GET | /assessment-reports?incident_id=&device_id= | 按事件/设备过滤历史报告 |

报告保留 `analysis_kind=rule_based`、`rule_version`、`is_simulated`、事件/运行/证据快照 ID、冻结观测、参考说明、趋势、判断、依据和信息缺口。接口原始 ID 里的 `demo` 是稳定技术标识，不能为修改展示文案而改写。
