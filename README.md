# 天亨 · 空天地人智能安全协同平台

校园安全 Agent 演示项目，2026-11-15 开始。当前已实现 **Day 1 智能工作台、Day 2 全域态势、Day 3 阶段一证据核查、Day 4 任务中心与空天地模拟执行、Day 5 全链路联调与交付验收**。页面研判仍是规则演示，真实模型自主规划尚未接入。

## 同事拉取与协作

仓库：<https://github.com/heqiucan/tianheng-skydome>。首次拉取后按下方“Windows 首次准备”安装依赖，再运行 `scripts/start.ps1`；无需模型密钥即可运行完整规则演示。协作流程、检查命令和素材边界见 [CONTRIBUTING.md](CONTRIBUTING.md)。

```powershell
git clone https://github.com/heqiucan/tianheng-skydome.git
Set-Location tianheng-skydome
```

仓库不包含虚拟环境、node_modules、运行数据库、日志、Cloudflare 可执行文件及临时分享地址。每位开发者首次启动时创建自己的演示数据库。产品使用的四张杭州校区底图和自有演示截图已保留；非运行必需的第三方参考截图、原始 PDF 和个人资料归档不上传，参考图集里的部分归档链接可能仅在原开发机可用。

## 当前能力与边界

用户操作请先阅读 [图文使用手册](docs/天亨SKYDOME使用手册.html) 或 [文字版手册](docs/天亨SKYDOME使用手册.md)。系统启动后可打开 [在线手册入口](http://127.0.0.1:5173/manual/index.html)。HTML 内嵌全部截图，可单文件离线阅读；包含启动、12 个操作章节、常见问题与能力说明。

- Vue / TypeScript 三栏工作台、全域态势总览、数字孪生地图、空天地协同视图；复用深蓝产品风格。
- 杭州校区两张规划鸟瞰图作为独立片区底图，两张透视图用于建筑详情；归一化坐标、缩放、拖动、全屏、九类独立图层。
- 统一设备和事件数据、设备趋势与抽屉、建筑模拟楼层、无人机航线草案/确认/动态进度/结果/历史及重复执行。
- 地图任务保存任务 ID、空间/设备/事件上下文，进入工作台展示规则研判并支持返回原选中对象；任务和巡检持久化到 SQLite。
- FastAPI + SQLite 保存统一的事件、监测记录、会话、运行和执行日志。
- 规则演示流程实际执行 `query_sensor_data`、`query_device_status`、`query_event_history`，产生有证据 ID 的演示风险初评。
- 模型工具调用探针单独验证真实 API；探针成功不等于模型已经接管页面中的工作流。
- 校园图片来自用户提供的学校规划资料，不能据此声称当前实景或真实三维模型。设备部署、监测值、事件、遥感覆盖和巡检航线均为模拟。
- 任务中心已实现人工/规则核查创建任务、三类资源选择、派发/执行/完成、取消/重试、地图联动及模拟执行报告 JSON 保存；状态、日志与报告由后端 SQLite 保存。
- Day 5 已实测 EVT-008 → TEMP-008 → 规则证据报告 → TASK-008 → UAV-003 → 执行报告 → 工作台反馈的 16 步闭环；服务重启后 19 项关联检查仍通过。
- 人工审批与风险关闭、真实模型自主规划、真实设备控制、正式研判 PDF 报告尚未实现；模拟执行完成不自动消除事件风险。

## Windows 首次准备

在项目根目录打开 PowerShell。需要 Node.js 24 和 Python 3.12（Day 2 已验证；原 Day 1 使用 3.13）；已有虚拟环境与依赖时不重复安装。

```powershell
py -3.12 -m venv .venv-day2
.\.venv-day2\Scripts\python.exe -m pip install -r backend\requirements.lock.txt
Set-Location frontend
npm ci
Set-Location ..
```

启动脚本优先使用 `.venv-day2`，不存在时回退 `.venv`。Windows Store Python 可能重定向 AppData；`scripts/migrate_store_runtime.py` 仅在目标数据库不存在时备份旧数据库到正常运行目录，保留源数据。

## 启动与停止

桌面已提供 **天亨 SKYDOME** 快捷方式：双击会启动本地服务并在默认浏览器打开系统；服务已运行时直接打开，不重复启动。失败时弹出提示并记录到 `%LOCALAPPDATA%\TianqiongDemo\desktop-launcher.log`。

如移动项目后需要重建桌面入口，在项目根目录运行 `scripts/install-desktop-shortcut.ps1`。快捷方式依赖本项目目录，请保留源文件和虚拟环境。

```powershell
.\scripts\start.ps1
```

- 页面：http://127.0.0.1:5173
- API 文档：http://127.0.0.1:8000/docs
- 默认数据库、日志、探针结果：`%LOCALAPPDATA%\TianqiongDemo`，避免运行数据库随 OneDrive 同步。
- 服务只监听本机，适用于单人演示；关闭浏览器不会停止服务。
- 启动脚本检查端口，不终止其他软件；无窗口后台启动两个服务。

```powershell
.\scripts\stop.ps1
```

停止脚本根据 PID、启动时间和可执行文件核对，只结束本项目记录的进程，不删除数据。

需要自定义数据目录时，在启动、停止、探针命令中保持一致的 `TIANQIONG_DATA_DIR`。不要同时从两台电脑访问同一个运行数据库。

## 演示顺序

1. 打开工作台，查看明确标识的模拟校园告警。
2. 选择当前事件，在输入框提交数据核查任务。
3. 展开过程面板，查看三项真实查询的结果与耗时。
4. 查看规则初评、证据和信息缺失项；到任务中心回看同一次运行。
5. 在设备中心和知识中心查询同一事件的数据和预置预案。
6. 启动新一轮演示场景，验证旧任务仍然保留。

流程可能很快完成：没有通过固定等待来伪造工具执行时间。

## Day 2 演示与参考素材

1. 点击一级导航「全域态势」，切换总览、数字孪生地图和空天地协同。
2. 点击建筑、设备或风险标记；在图层列表中验证显示开关，使用缩放、拖动和全屏。
3. 在空天地协同选择无人机和目标建筑，生成航线后确认；12 秒为演示时长，完成后可重新执行。
4. 从地图提交 Agent 分析任务，进入工作台查看绑定对象和证据；刷新页面，再返回地图。
5. 地面机器人展示待命任务和进度，卫星展示模拟覆盖与待命状态；没有真实遥感影像或机器人执行控制。

- 截至 Day 5，本对话 12 张用户截图、图集 11 张图片及 Day 1 实际截图共 24 张已分类保存到 `public/references/`。设计截图用于布局、调度与路线表现参考，不替换学校规划底图。
- [素材浏览页](http://127.0.0.1:5173/references/index.html)、[逐图分析](docs/参考素材分析表.md)、[Day 2 验收报告](docs/day2-acceptance.md)。
- 长兴图片仅归档；杭州两张不同年份的鸟瞰图独立展示，不拼接为未经核实的全校园地图。公寓楼层资料冲突，教学楼名称/位置及真实楼层图仍待核实。
- 初始事件为三个；已有 Day 1 历史事件和任务予以保留，因此实际统计可能更多。所有组件从统一数据源计算。

## Day 4 任务中心与协同执行

1. 任务中心 → 执行任务 / 协同资源 / 历史分析；原来的核查与地图分析记录保留在历史分析中。
2. 从已完成的证据规则核查点击「根据规则核查创建执行任务」，或在任务中心手动创建任务。
3. 在任务详情选择适配资源、保存分配、开始执行；模拟调度 3 秒、执行 24 秒，计时不代表实际作业时长。
4. 点击「查看地图与路线」观察无人机位置与进度；完成后查看、下载任务专属 JSON 报告。
5. 从来源核查回看关联任务和执行结果；取消会冻结进度，重新执行会建立新任务并保留旧记录。

执行任务由服务端统一管理。进度在查询时按保存时间推进，刷新或重启后会计入已过去的时间；这不是持续后台作业系统。三个页面共用同一份执行状态，原 Day 2 巡检与 Day 4 共用资源占用约束。

- [Day 4 验收与文件清单](docs/day4-acceptance.md)、[接口与数据契约](docs/day4-contract.md)、[参考素材分析](docs/day4-reference-analysis.md)。
- 前端沿用内部页面切换：浏览器地址仍为 `/`，不新增路由框架。任务中心、工作台、地图由页面状态与对象 ID 联动。

## Day 5 最终交付

- [最终 A–J 交付报告](docs/day5-final-delivery.md)、[验收索引](docs/day5-acceptance.md)、[DAY 05 联调契约](docs/day5-contract.md)。
- [重启后运行验证](docs/day5-after-restart.json)、[飞行位置采样](docs/day5-flight-observations.json)、[截图目录](docs/screenshots/)。
- 任务中心显示 7 个持久化执行任务，其中 6 个已完成、1 个已取消；TASK-008 已完成 100%，风险事件保持开放并标注人工复核。

## 模型验证

模型密钥只在后端或独立探针中使用，不进入浏览器。不要把密钥写进本 README、源文件、日志或聊天。

探针需要智谱标准 API 可用权限；本机启动不自动调用付费模型。命令示例（只传文件路径，不传密钥值）：

```powershell
.\.venv\Scripts\python.exe scripts\probe_model.py --key-file "$env:USERPROFILE\OneDrive\Desktop\智谱key.txt" --output "$env:LOCALAPPDATA\TianqiongDemo\model_probe.json"
```

最多两次模型请求：获取工具调用、执行本地模拟传感器查询、回传工具结果并核对结构化事实。仅保存脱敏状态、工具名称、用量和耗时；不保存密钥、模型原始回复或隐藏推理。具体结果以 `docs/progress.md` 的实际验收记录为准。

## 验证

```powershell
.\.venv-day2\Scripts\python.exe -m pytest -q --basetemp=.pytest-temp -p no:cacheprovider
Set-Location frontend
npm run build
node --test tests/map-geometry.test.mjs tests/assessment-selection.test.mjs tests/presentation-text.test.mjs
```

测试使用临时数据库，不修改演示数据。`/health` 只证明进程存活，浏览器操作和数据一致性仍需单独验收。

## 上游与本地实现

参考 [Vue](https://github.com/vuejs/core)（MIT）、[Vite](https://github.com/vitejs/vite)（MIT）、[FastAPI](https://github.com/fastapi/fastapi)（MIT）、[Pydantic](https://github.com/pydantic/pydantic)（MIT）、[HTTPX](https://github.com/encode/httpx)（BSD-3-Clause）、[智谱工具调用协议](https://docs.bigmodel.cn/cn/guide/capabilities/function-calling)。SQLite 为 Public Domain。

参考 [SVG viewBox](https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Attribute/viewBox) 将图片与交互图层放在同一坐标系。校园素材来源见逐图分析表，参考截图仅借鉴设计语言。

页面视觉、图片地图及标记避让、工具执行、上下文关联、规则初评、巡检状态机、场景隔离和本地启动脚本为本项目实现。没有引入 Three.js、Cesium、Element Plus、ECharts 或 LangGraph；实际依赖以锁定文件为准。
