# 天亨 SKYDOME · DAY 04 交付与验收

验收日期：2026-11-15。环境：Windows 本机，Vue 3.5.45 / Vite 7.3.8 / TypeScript 5.9.3，FastAPI 0.163.0 / SQLite，沿用 `.venv-day2` Python 3.12。没有新增运行依赖。

## 交付结论

任务中心、资源分配、状态流转、结果保存和跨页面联动已实现并实际运行。无人机、地面机器人、卫星遥感均为模拟流程。源头兼容 Day 3 阶段一已经保存的规则核查结果；真实模型研判与自主规划未接入，不纳入本次完成结论。

产品界面统一为「天亨」，移除英文 DEMO 展示标签，保留中文模拟/演示说明。稳定设备 ID、旧数据库目录、接口字段、不可变证据内容保留兼容；原始接口记录可能包含旧技术标识。

## 功能与页面入口

| 入口 | 已交付内容 |
|---|---|
| 任务中心 → 执行任务 | 统一统计、搜索、状态/类型筛选、创建、详情、资源选择、开始、取消、重试、日志、报告 |
| 任务中心 → 协同资源 | UAV-003、ROBOT-002、SAT-001 的能力、在线/占用状态、关联任务 |
| 任务中心 → 历史分析 | 保留前三天分析运行与地图任务入口 |
| 智能工作台 → 事件证据核查 | 根据已保存规则核查创建任务，回看关联执行进度和报告入口 |
| 全域态势 → 数字孪生地图 / 空天地协同 | 任务目标、起点、归一化路线、无人机位置、任务状态和资源联动 |

前端沿用 `App.vue` 的内部页面状态：`workbench`、`tasks`、`map`，地址仍为 `http://127.0.0.1:5173/`，没有虚构 `/tasks` 页面 URL。API 文档为 `http://127.0.0.1:8000/docs`。

## 数据与状态

- 新增执行任务与冻结来源存储；任务关联 `incident_id`、`device_ids`、`target_building_id`、`source_run_id`、`evidence_snapshot_id`、`resource_id`、`parent_task_id`。
- 后端负责状态、进度、时间、步骤、日志与完成报告。状态为 pending → dispatching → running → completed，并支持 cancelled、failed。
- SQLite 事务与唯一约束保护资源占用和幂等创建；原 Day 2 巡检和新任务不能同时占用同一无人机。
- Vue `execution.ts` 提供共享响应式任务与资源；活动时约 900 ms、空闲时约 4 s 同步。浏览器保存选中任务 ID，业务数据由后端恢复。
- 3 秒模拟调度 + 24 秒模拟执行。按保存的服务端时间在查询时推进；关闭页面或重启服务后会计入经过的时间。没有常驻任务工作进程，也不代表物理设备持续作业。
- UAV-003 映射旧设备 DRONE-001，ROBOT-002 映射旧设备 ROBOT-001；保留稳定设备 ID。SAT-001 没有虚构路线或影像。
- 取消冻结进度并释放资源。重试生成新子任务，不覆盖旧报告。完成只记录待人工复核，不自动消警。

## 实际浏览器验收

| 操作 | 实际结果 |
|---|---|
| 从保存的规则核查创建 | 生成 TASK-001，绑定 run-c1b19372dcc2492a、evidence-99d4647d2f3544ba 与原事件 |
| 同来源、同类型再次创建 | 打开原 TASK-001；总任务数仍为 6，没有重复派发 |
| 选择 UAV-003 并启动 | 观察到派发中，随后地图显示占用资源、路线和执行进度 |
| 无人机地图动画 | 连续读取 0%、9.92%、21.67%、31.05% 及变化的 SVG 坐标；已保存运行截图 |
| 取消执行 | TASK-004 停止在 45.18%，后续刷新与重启仍保持该进度，资源释放 |
| 重试 | TASK-002 / TASK-004 分别关联原任务，旧任务及已完成报告保留 |
| 手动创建并执行 | TASK-003 无人机、TASK-005 地面巡检、TASK-006 模拟遥感均完成 |
| 完成结果 | 5 项完成任务产生 5 个不同报告 ID；内容绑定各自资源、事件、时间和范围 |
| 报告保存 | TASK-001 报告已通过浏览器下载为「天亨-TASK-001-模拟执行报告.json」，解析验证关联 ID 与 requires_human_review |
| 返回来源工作台 | 显示 TASK-001 / TASK-002 已完成 100% 和已有执行报告，并能进入任务详情 |
| 关联设备定位 | 任务详情点击 dev-temp-01 后，地图选中 TEMP-008，显示 68.5℃ 与模拟楼层说明 |
| 搜索与筛选 | 搜索 TASK-004、切换已完成筛选、恢复全部状态有效 |
| 服务重启 | 终态任务、5 个报告、取消进度与旧数据恢复；资源可用，原事件仍 open |
| 布局与品牌 | 1440×900 检查任务/资源/地图；390×844 DOM 无页面横向溢出，导航折叠后补充可访问名称；不视为完整手机端专项验收 |

运行数据核对见 [day4-runtime-verification.json](day4-runtime-verification.json)，前后基线见 `day4-baseline.json`、`day4-before-restart.json`。本次服务重启时任务均已进入终态；执行中重启恢复由自动测试覆盖，不冒充浏览器实测。

## 自动验证

- 后端完整回归：**56 passed**，其中 Day 4 参数化用例共 11 项；1 条既有 Starlette / HTTPX 弃用提示。
- 覆盖从核查创建资格、非法 ID、幂等、冻结来源、状态与日志、执行中重启恢复、取消/重试、并发启动及新旧巡检互斥、离线/类型/未知位置拒绝、中途离线失败、地面/遥感边界。
- 地图几何：**3 passed**，覆盖按段长移动、空/重复坐标和拖动边界。
- `npm run build`：TypeScript 校验与 Vite 生产构建通过。
- 浏览器没有手工执行设备离线注入、并发竞态、断网乱序、多实例或压力测试；不要将这些自动测试/代码保护表述为全部浏览器验收。

## 文件清单

| 新增 / 修改 | 文件 | 作用 |
|---|---|---|
| 新增 | backend/app/execution.py | 任务生命周期、资源、冻结上下文、日志、报告 |
| 新增 | backend/app/spatial.py | 新旧地图路线及进度共用 |
| 修改 | backend/app/database.py | 持久化与幂等/互斥约束 |
| 修改 | backend/app/schemas.py、main.py、situation.py | 请求校验、API、地图/资源同步与品牌 |
| 新增 | backend/tests/test_day4_execution.py | 执行闭环与回归测试 |
| 新增 | frontend/src/execution.ts | 任务/资源类型、共享状态、轮询与报告保存 |
| 新增 | frontend/src/components/TaskCenter.vue、ExecutionTaskDetail.vue | 任务中心、资源与任务详情 |
| 新增 | frontend/src/day4.css | 深蓝风格与响应式布局 |
| 修改 | frontend/src/App.vue | 页面集成、导航和异步响应保护 |
| 修改 | frontend/src/components/EvidenceWorkbench.vue | 来源核查创建任务、回看结果 |
| 修改 | frontend/src/components/SituationView.vue、CampusImageMap.vue | 任务地图路线、移动和协同资源 |
| 修改 | frontend/src/components/MapTaskWorkbench.vue | 品牌及历史文本展示 |
| 修改 | frontend/src/api.ts、situation.ts、frontend/index.html | 展示兼容、类型、页面标题 |
| 新增 | public/references/ui/04_task_command_reference.png | 任务布局参考 |
| 新增 | public/references/interaction/03_air_ground_dispatch.png、04_patrol_route_dashboard.png | 调度与路线参考 |
| 修改 | public/references/inventory.json、index.html | 23 张参考素材索引 |
| 修改 | scripts/write_reference_analysis.py、docs/参考素材分析表.md、.gitignore、README.md、docs/api.md、docs/progress.md | 23张素材可重复生成、品牌、测试临时目录、使用与接口进度说明 |
| 新增 | docs/day4-contract.md、day4-reference-analysis.md、day4-acceptance.md | 实现契约、素材检查与验收 |
| 新增 | docs/day4-baseline.json、day4-before-restart.json、day4-runtime-verification.json | 运行数据保留证据 |
| 新增 | docs/screenshots/day4-task-center.jpg、day4-resources.jpg、day4-flight-running.jpg | 实际页面和执行截图 |

仓库在接手时尚无可用提交基线，因此以上按本轮实施记录归类，未把整个仓库的未跟踪状态当作全部新增。本轮未提交或推送 Git。

## 未完成与边界

1. Day 3 真实模型研判、自主选择工具与行动规划尚未接入；现有创建来源清晰标为规则核查。
2. 没有真实无人机、机器人、卫星控制或新现场数据；示意路线没有空域/避障/道路可达性校核。
3. 执行结果保存为 JSON；正式研判 PDF、人工审批、人工复核录入与风险关闭流程未实现。
4. P2 高级统计与历史分析图表未扩展；历史分析页当前用于保留已有记录。
5. 本地单实例演示，未做生产部署、多用户权限、压力与移动端完整专项验收。

## 用户复测步骤

1. 打开首页 → 任务中心，查看 6 条已保存任务及「协同资源」。
2. 打开 TASK-001，查看日志和执行报告；展开来源，返回规则核查，确认关联任务可见。
3. 点击「创建执行任务」，输入名称、选择已有实训基地事件和「无人机巡检」，创建后选择 UAV-003 并保存。
4. 点击「开始执行」，立即点击「查看地图与路线」，观察约 27 秒模拟流程；完成后回到详情保存报告。
5. 新建重试任务并启动，在执行中取消，确认进度停止、资源恢复可用，旧报告保留。
6. 刷新页面，再次打开任务和报告；检查「全域态势」事件仍待人工核查。

## 上游参考

沿用 Vue 官方共享响应式状态方法（MIT，https://github.com/vuejs/core）、FastAPI 请求校验与接口组织（MIT，https://github.com/fastapi/fastapi）、SQLite 原子事务（Public Domain，https://www.sqlite.org/lang_transaction.html）。执行生命周期、兼容旧巡检的资源互斥、冻结来源、报告与归一化地图联动均针对本项目实现；没有引入调度框架或三维引擎。
