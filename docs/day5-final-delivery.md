# 天亨 SKYDOME Agent · DAY 05 最终交付报告

验收范围：杭州校区演示场景、EVT-008/TEMP-008/TASK-008/UAV-003 业务闭环、四天已有页面联动，以及本地服务重启后的数据恢复。校园图片来自用户提供的学校规划资料，不能视为当前实景或真实三维模型；设备部署、监测值、事件和资源执行均明确标注为模拟或演示能力。

## A. 项目总体完成情况

DAY 05 已完成从风险发现到执行反馈的本地可操作闭环：地图建筑与设备 → EVT-008 → TEMP-008 设备详情 → 证据核查与三项后端工具 → 结构化规则研判报告 → TASK-008 → UAV-003 模拟调度与巡检 → 执行报告 → 工作台和地图回看。

当前运行数据在服务重启后仍保留：8 起事件、9 次核查运行、7 个执行任务；TASK-008 已完成 100%，原 EVT-008 仍保持待人工复核的开放状态。执行完成不会自动关闭风险事件。

真实大模型尚未接入工作台的研判流程。当前使用后端真实查询接口、冻结证据快照和明确版本的规则演示；独立模型探针的成功不代表页面已经由模型自主规划。

## B. 页面及路由清单

项目采用单页内部状态切换，没有 Vue Router，也没有 `/tasks`、`/risk` 这类独立 URL。页面状态保存在 `page` 和本地缓存中，刷新后恢复可用页面。

| 页面 | 内部 key | 主要内容 |
|---|---|---|
| 智能工作台 | `workbench` | 基础核查、证据核查、任务来源反馈 |
| 任务中心 | `tasks` | 执行任务、协同资源、历史分析、报告 |
| 风险研判 | `risk` | 已保存规则研判报告、历史选择、关联任务 |
| 智能体编排 | `flow` | 当前固定工具流程与未建设能力说明 |
| 全域态势 | `map` | 总览、数字孪生地图、空天地协同 |
| 设备中心 | `devices` | 设备状态、参考规则、关联事件与 Agent 入口 |
| 知识中心 | `knowledge` | 本地演示资料检索与原文查看 |
| 智能实训 | `training` | 独立模拟场景入口 |
| 系统管理 | `settings` | 服务、数据库和能力状态 |

全域态势内部视图为 `overview`、`map`、`coordination`，使用同一份后端态势数据。

## C. 已完成的核心功能

- 显式准备、幂等读取 EVT-008 场景；不在刷新或启动时偷偷重置数据。
- TEMP-008 设备详情显示 68.5℃、采样时间、质量、当前状态、模拟规则参考和关联事件选择。
- 证据核查真实执行 `query_sensor_data`、`query_device_status`、`query_event_history`，保存工具状态、耗时、证据 ID 与事件日志。
- 报告保存温度趋势、关联设备证据、风险判断、可能原因、不确定性、建议、规则版本和信息缺口；报告与核查结果在同一事务中保存。
- 从同一核查创建 TASK-008，保留事件、设备、建筑、证据快照和来源运行的关联。
- 任务中心支持列表、详情、资源选择、分配、派发、执行、取消、重试、日志和结果报告。
- UAV-003 模拟路线按归一化地图坐标移动，地图位置和任务进度随执行查询变化；完成后生成专属 JSON 执行报告。
- 工作台、风险研判、任务中心、地图、设备中心使用稳定 ID 关联；刷新和服务重启后可读取已保存结果。
- 知识检索无结果空态、失效页面缓存回退、异步旧响应防护、全屏失败反馈和详情抽屉边界已补齐。

## D. 核心业务链路验收结果

已在本地浏览器实际操作 16 步：启动 → 工作台 → 全域态势 → 物流与航空实训基地 → TEMP-008 → EVT-008 → Agent 三项查询 → 规则报告 → 创建 TASK-008 → 任务中心 → UAV-003 → 启动巡检 → 地图路线与进度 → 完成 → 执行报告 → 返回工作台反馈。

| 验收项 | 结果 | 证据 |
|---|---|---|
| 建筑和真实规划底图显示 | 通过 | `screenshots/day5-flight-running.jpg` |
| TEMP-008 当前读数与关联事件 | 通过 | `screenshots/day5-device-evidence.jpg` |
| 三项后端工具与工具记录 | 通过 | `docs/day5-runtime-verification.json` |
| 结构化风险研判报告 | 通过 | `screenshots/day5-assessment-report.jpg`、报告 JSON |
| TASK-008 创建与 UAV-003 调度 | 通过 | `screenshots/day5-task-center-completed.jpg` |
| 路线、位置、进度变化 | 通过 | `docs/day5-flight-observations.json`、运行中截图 |
| 工作台回看执行反馈 | 通过 | `screenshots/day5-workbench-feedback.jpg` |
| 服务重启后关联和历史保留 | 通过 | `docs/day5-after-restart.json` 的 19 项检查 |

后端自动回归为 **67 passed**（原有 56 + DAY 05 新增 11）；前端几何、研判选择和文案回归为 **7 passed**；最终 `npm run build` 通过，Vite 构建 45 个模块。

额外实际操作：九个一级导航均打开；设备无结果检索与详情关闭、知识检索/原文/无结果恢复、任务详情与报告打开、报告 JSON 下载，以及待执行/执行中刷新均已核对。开发中出现的热更新错误在完整重载后消失；最终重载后没有新增 error 级控制台记录。异常输入、错误关联、并发幂等和失效导航主要由自动测试验证，未穷举所有按钮组合、网络断线和浏览器版本，不把这些范围写成已全面验收。

## E. 跨页面数据联动

| 稳定对象 | 关联页面和状态 |
|---|---|
| EVT-008 / `inc-demo-evt-008` | 地图标记、设备关联事件、工作台证据、风险报告、TASK-008 来源 |
| TEMP-008 / `dev-temp-01` | 地图、设备详情、6 条冻结证据记录、报告和任务设备列表 |
| TASK-008 / `execution-1e2dff31881b4fd3` | 工作台、任务中心、地图路线、执行报告 |
| UAV-003 | 资源面板、任务详情、模拟路线与任务日志 |

服务端 SQLite 是任务、运行、快照和报告的持久化来源；页面只保存当前选择和返回位置。`docs/day5-after-restart.json` 检查了事件、运行、任务、地图任务、巡检和旧快照未被新场景改写。

执行进度在服务端查询时根据已保存的开始时间推进，浏览器轮询读取并插值显示地图位置。刷新或重启不会把任务重新置零，但这不是持续后台作业或真实设备遥测。

## F. 本次修复的问题

- 修复展示文案替换会把 `inc-demo-evt-008` 误改成 `inc-模拟-evt-008` 的问题；独立展示词可转换，技术 ID 保持原样。
- 补齐知识中心无匹配资料的计数、空态和清空搜索操作。
- 关闭知识中心、编排、设置等页面误显示旧 DAY 01 执行侧栏的问题；旧过程只在基础工作台且没有当前证据/地图任务时显示。
- 保留报告异步轮询、设备请求代次保护、无效缓存页面回退和任务详情的可滚动边界。

## G. 未完成的功能及原因

- 页面研判仍是规则演示，不是大模型自主分析；原因是工作台尚未接入模型调用、工具选择和审批链。
- 无真实校园物联网设备、视频流、无人机、机器人或卫星接口；当前资源和路线只模拟状态与进度。
- 没有人工审批、风险关闭工作流、正式 PDF 报告、生产权限、多人协同和公网部署。
- 建筑楼层、真实设备部署和正常工程参考范围仍需学校资料或设备规范确认；报告对此保留不确定性，不将 60℃阈值称为消防标准。
- 当前页面是单页状态切换，没有独立深链接 URL；这属于现有架构约束。

## H. 真实能力、模拟能力、规划能力

| 类型 | 当前范围 |
|---|---|
| 真实能力 | FastAPI 接口、SQLite 持久化、三项查询工具、事件/设备/快照/报告/任务关联、状态机、浏览器可操作联动 |
| 模拟能力 | 校园图像底图上的空间标记、监测值、风险事件、规则阈值、无人机/机器人/卫星资源、路线移动和执行报告 |
| 规划能力 | 已保存后续核查建议和任务计划入口；尚未提供模型自主规划、正式预案决策或真实资源控制 |

## I. 启动方式和运行环境

- Windows PowerShell，Node.js 24.14.1，Python 3.12.14。
- Vue 3.5.45、Vite 7.3.8、TypeScript 5.9.3、FastAPI 0.163.0、SQLite；版本以锁定文件和当前环境为准。
- 启动：`.\scripts\start.ps1`。
- 页面：http://127.0.0.1:5173；API 文档：http://127.0.0.1:8000/docs。
- 运行数据：`%LOCALAPPDATA%\TianqiongDemo`；停止：`.\scripts\stop.ps1`。
- 前端验证：`npm run build`；回归：`node --test tests/map-geometry.test.mjs tests/assessment-selection.test.mjs tests/presentation-text.test.mjs`。
- 后端验证：`.\.venv-day2\Scripts\python.exe -m pytest -q --basetemp=.pytest-temp -p no:cacheprovider`。

## J. 最终 Demo 演示流程

1. 打开工作台，点击“准备 EVT-008 演示链路”，进入全域态势并定位物流与航空实训基地。
2. 点击 TEMP-008，查看 68.5℃、模拟参考、采样记录，选择 EVT-008 并进入 Agent 核查。
3. 执行三项查询，展开工具记录，查看规则研判报告中的趋势、证据、风险判断和信息缺口。
4. 在报告下方创建执行任务；任务中心打开 TASK-008，选择 UAV-003 并保存资源。
5. 点击开始执行；查看派发、执行、日志和地图路线，等待 100% 完成。
6. 打开执行报告，再回到工作台查看“已有执行报告待人工复核”的 TASK-008 卡片。
7. 如需再次演示，使用“新建重试任务”生成新的任务编号；不要把重试任务重新称为 TASK-008。

交付文件还包括 [DAY 05 联调契约](day5-contract.md)、[运行验证 JSON](day5-runtime-verification.json)、[重启后验证 JSON](day5-after-restart.json)、[飞行采样记录](day5-flight-observations.json) 和 `screenshots/` 下的实际操作截图。两份实际下载报告同时保存在 `docs/deliverables/` 与用户 Downloads 目录，文件名分别为 `天亨-规则研判报告-assessment-report-175120c152ba4db6.json` 与 `天亨-TASK-008-模拟执行报告.json`。

## 本次文件清单

后端新增：`backend/app/demo_scenario.py`、`backend/app/rules.py`、`backend/app/assessment.py`、`backend/tests/test_day5_delivery.py`。

后端修改：`backend/app/main.py`、`database.py`、`schemas.py`、`evidence.py`、`workflow.py`、`execution.py`、`situation.py`、`fixtures.py`。

前端新增：`frontend/src/assessmentSelection.ts`、`frontend/src/day5.css`、`frontend/src/components/AssessmentReportView.vue`、`DeviceCenter.vue`、`DeviceAnalysisPanel.vue`、`frontend/tests/assessment-selection.test.mjs`、`presentation-text.test.mjs`。

前端修改：`frontend/src/App.vue`、`api.ts`、`evidence.ts`、`situation.ts`、`execution.ts`、`frontend/src/components/EvidenceWorkbench.vue`、`IncidentEvidencePanel.vue`、`SituationView.vue`、`CampusImageMap.vue`、`ExecutionTaskDetail.vue`。

根目录及资料：`.gitignore`、`README.md`、`scripts/start.ps1`、`scripts/verify_day5_runtime.py`、`scripts/write_reference_analysis.py`、`docs/progress.md`、`docs/day5-contract.md`、`docs/day5-reference-analysis.md`、`docs/day5-final-delivery.md`、`docs/day5-acceptance.md`、DAY 05 验证 JSON/截图、`docs/参考素材分析表.md`、`public/references/inventory.json`、`public/references/index.html`、`public/references/visual/04_campus_command_cockpit.png`。

上游只读参考 Vue 的异步清理和组件状态模式、SQLite 事务约束；证据选择、报告结构、规则、固定场景、任务状态机与地图联动均为本项目实现。没有新增大型地图或 Agent 框架依赖，也没有推送代码或修改上游仓库。
