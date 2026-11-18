# DAY 03 第一阶段验收记录

验收日期：2026-11-15。范围：事件详情、统一数据口径、持久化证据快照、三工具实际查询，以及地图与工作台之间的往返。仅代表第一阶段技术验收通过，DAY 03 整体验收仍待后续真实模型、任务计划和报告阶段完成。

## 当前可操作路径

本地页面：http://127.0.0.1:5173/ 。接口文档：http://127.0.0.1:8000/docs 。保持 Vue 3 / TypeScript / Vite 与 FastAPI / SQLite 技术栈。

1. 全域态势 → 数字孪生地图 → 点击风险事件。
2. 在详情中核对事件编号、来源、时间、区域、状态及关联设备。
3. 切换“事件关联证据 / 当前设备状态”，查看不同时间口径。
4. 点击“发起研判 · 证据核查”，由服务端生成证据快照并进入智能工作台。
5. 执行三项查询，查看真实工具返回、耗时、观测来源 ID 和规则核查结果。
6. 保存证据核查 JSON，或返回原地图视图与原事件。
7. 通过“创建单温异常场景（DEMO）”新增对照事件，不覆盖旧事件。

## 本阶段交付

- 事件上下文与地图当前指标共用设备关联、最新观测排序和状态计算逻辑。
- 事件证据保留采样时间、观测 ID、设备 ID、事件 ID、数据质量和口径。
- SQLite 在同一事务内保存事件、设备、观测及历史事件快照；数据库触发器禁止改写已保存快照。
- 核查运行绑定快照；监测数据查询、关联设备查询和历史事件检索全部读取同一份已保存内容。
- 前端只缓存恢复用 ID；刷新后从后端恢复快照与运行记录。
- 支持同一快照重新运行、选择历史运行、三个来源视图往返恢复。
- 独立 evidence_checks 回显证据核查状态，不混入第四天执行任务。
- 校验不存在的事件/快照、事件与快照不匹配、错误底图及伪造请求字段。
- 保留第一天基础工作台和第二天原有地图、图层、地图任务、巡检数据。

## 真实操作结果

| 检查 | 结果与证据 |
|---|---|
| 地图打开旧事件 | inc-demo-001，事件详情字段完整；事件温度为 78℃，烟雾告警，当前设备状态与历史事件分开显示 |
| 旧事件三工具核查 | evidence-4c1a5d6df753402e → run-3b454709f0cb41f8；3 条 tool_result，结果为高风险、多源异常需要优先人工复核 |
| 新建单温对照事件 | inc-temp-6151439068f444c9；68.5℃、烟雾未触发、CAM-021 在线且无异常记录 |
| 对照事件三工具核查 | evidence-99d4647d2f3544ba → run-b1e1bc9feab5400d；结果为中风险、单项异常需要补充核查，未声称确认火灾 |
| 同快照重新核查与历史切换 | 第二次 run-c1b19372dcc2492a；在两次历史运行之间切换，指令、运行 ID 和耗时记录同步切换 |
| 刷新及服务重启 | 快照、结果和完整 3 条工具记录可恢复；旧快照 checksum 不变，仍保存 78℃ |
| 返回来源 | 数字孪生地图、全域态势总览、空天地协同分别往返测试通过；保留来源视图、底图与原事件选择 |
| 关联范围 | inc-demo-offline 详情只关联 CAM-021；inc-demo-fire 只关联 FIRE-003，未扩大成同层全部设备 |
| 地图回显 | 完成运行后显示“证据核查完成，待模型研判”，未把规则初评标成真实模型完成 |
| 地图图层回归 | 关闭温度图层后 TEMP-008 地图标记为 0 个，重新开启恢复 1 个 |
| 第一天回归 | 从任务中心打开 run-fd9f6bb111ed48c0，原基础核查工作台及完成结果正常显示 |
| 保存记录 | 浏览器成功下载核查 JSON；内含 snapshot、run、3 条 tool_result、1 条 terminal，明确非真实模型研判报告 |
| 响应式 | 1440×900 桌面双列与 390×844 窄屏单列检查通过；窄屏 document.scrollWidth=390，无可见横向溢出；验收后恢复浏览器尺寸 |
| 控制台 | 最终检查未捕获 error 级日志 |

证据文件：`day3-stage1-baseline.json`、`day3-stage1-old-snapshot.json`、`day3-stage1-runtime-verification.json`。原有 32 条观测逐字段核对未变化；原有事件、地图任务、巡检和核查 ID 均保留。运行期间可以继续创建 DEMO 场景，因此当前总数不作为固定验收阈值。

截图：`screenshots/day3-stage1-workbench.jpg`、`screenshots/day3-stage1-result.jpg`、`screenshots/day3-stage1-mobile.jpg`。

## 自动验证

```powershell
.\.venv-day2\Scripts\python.exe -m pytest -q --basetemp=.pytest-day3-final -p no:cacheprovider
cd frontend
npm run build
```

- 最终后端：45 项通过，包含原有 37 项回归及新增 8 项。
- 保留 1 条既有 Starlette TestClient/httpx 弃用提示，不影响本次通过；本次未为消除提示变更依赖。
- TypeScript 检查及 Vite 生产构建通过，无新增重量依赖。
- 新增测试覆盖混合时区绝对时间排序、同时间稳定排序、地图/上下文一致性、快照冻结后原数据变化、三工具固定快照、请求拒绝、对照场景以及地图核查状态。
- 取消、失败、重启中断路径由自动化回归覆盖；本次没有对每种失败路径再做浏览器人工注入。

## 修改文件

| 文件 | 用途 |
|---|---|
| backend/app/evidence.py（新增） | 统一事件上下文、指标、关联、时间排序与快照服务 |
| backend/app/database.py | 快照表、兼容迁移、不可变触发器与排序修正 |
| backend/app/fixtures.py | 显式创建 68.5℃单温对照场景 |
| backend/app/main.py | 上下文、快照和场景接口 |
| backend/app/schemas.py | 快照与运行请求校验 |
| backend/app/workflow.py | 三工具绑定快照、结果保留证据引用 |
| backend/app/situation.py | 地图共用指标逻辑，增加 evidence_checks |
| backend/tests/test_day3_context.py（新增） | 第一阶段后端验收测试 |
| frontend/src/evidence.ts（新增） | 统一前端证据类型与展示格式 |
| frontend/src/components/IncidentEvidencePanel.vue（新增） | 完整事件详情与两种证据口径 |
| frontend/src/components/EvidenceWorkbench.vue（新增） | 三工具查询、历史恢复、结果与导出 |
| frontend/src/day3.css（新增） | 深蓝视觉与响应式样式 |
| frontend/src/App.vue | 工作台入口、历史切换、刷新恢复及请求竞态保护 |
| frontend/src/components/SituationView.vue | 对照场景入口、事件面板、时间轴状态 |
| frontend/src/api.ts、frontend/src/situation.ts | 快照引用与地图状态类型 |
| .gitignore | 忽略 DAY 03 测试临时目录 |
| docs/day3-stage1-contract.md（新增） | 阶段接口与数据口径约定 |
| docs/day3-stage1-acceptance.md 及上述 JSON/截图（新增） | 验收记录与证据 |

## 实现参考与后续边界

只读核对 FastAPI 官方仓库（https://github.com/fastapi/fastapi，MIT）、Pydantic 官方仓库（https://github.com/pydantic/pydantic，MIT）以及 SQLite 事务隔离说明（https://www.sqlite.org/isolation.html）。沿用项目现有版本及类型校验机制，快照、设备关联规则和页面交互针对本项目自行实现。未复制第三方产品页面，未增加三维引擎，也未更换校园素材。

当前为 DEMO 数据 + 实际数据库查询 + 固定三工具流程 + 明确标注的演示规则。没有调用智谱模型，没有生成可执行的第四天任务计划；导出是证据核查 JSON，不是最终研判报告。界面允许填写核查目标，但目前不会让模型理解指令或自主选工具，这属于下一阶段。

下一阶段：把已固定的证据交给真实智谱模型，保留实际模型/工具调用记录并验证结构化输出；用上述两种场景验收证据引用、风险区别、信息缺口及调用失败反馈。之后再实现最小任务计划与创建接口、研判报告。完整无人机执行仍归第四天。
