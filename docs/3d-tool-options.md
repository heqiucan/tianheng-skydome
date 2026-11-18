# 三维工具与 MCP 选型记录

核验日期：2026-11-15。本次实时只读查阅维护者仓库、正式发布页、许可证与官方文档；没有安装下列工具、修改 MCP 配置或调用三维生成服务。版本是核验当天的结果，后续接入前应重新确认。

## 1. 候选比较

| 候选与上游 | 本次核实的版本 / 许可证 | 用途 | 本项目适配判断与限制 |
|---|---|---|---|
| [Three.js](https://github.com/mrdoob/three.js) | 最新 GitHub Release 为 [r187](https://github.com/mrdoob/three.js/releases/tag/r187)；[MIT](https://raw.githubusercontent.com/mrdoob/three.js/r187/LICENSE) | 浏览器三维场景渲染；官方 GLTFLoader 能加载 glTF 2.0 资产及相关扩展 | 将来有可靠建筑模型时，可用于局部校园或楼栋的旋转、点选、高亮。它不会从效果图自动恢复准确建筑结构；需要自行控制模型体积、贴图与资源释放。当前图片地图不必为此增加依赖。 |
| [CesiumJS](https://github.com/CesiumGS/cesium) | 最新 GitHub Release 为 [1.147](https://github.com/CesiumGS/cesium/releases/tag/1.147)，发布页日期 2026-11-02；[Apache-2.0](https://raw.githubusercontent.com/CesiumGS/cesium/1.147/LICENSE.md) | 地理空间三维地球与地图、WGS84 定位、3D Tiles 等数据展示 | 将来有测绘坐标、地形、倾斜摄影或地理配准后的校园模型时更适合。当前归一化图片坐标不能直接当作经纬度，规划效果图也不是正射影像。引擎开源与外部地形、影像、Cesium ion 服务的授权及费用是不同事项。 |
| [社区 MCP for Blender](https://github.com/ahujasid/mcp-for-blender)，原 `ahujasid/blender-mcp` | `pyproject.toml` 和 PyPI 均为 **2.2.9**；PyPI 发布日期 2026-11-13；MIT。GitHub Releases 页面明确没有正式 Release，不能把 main 分支当作 GitHub 稳定发布标签 | 让 Agent 通过 Blender 插件读取/修改场景、执行 Blender Python、检查视图与渲染；实际建模由 Blender 完成 | 适合以后清理已取得的模型、规范对象命名、制作明确 DEMO 的设备模型和导出前检查。上游有 Windows 与 Codex 接入说明，但本项目尚未安装或实测。它是社区集成，与 Blender Foundation 无隶属关系，不能称为 Blender 官方 MCP。 |

Three.js 的资产加载能力依据 [GLTFLoader 官方文档](https://threejs.org/docs/pages/GLTFLoader.html)。Cesium 的地理数据与可选云服务边界依据 [官方 README](https://github.com/CesiumGS/cesium#readme)。MCP 版本依据 [上游 pyproject.toml](https://raw.githubusercontent.com/ahujasid/mcp-for-blender/main/pyproject.toml)、[PyPI 发布历史](https://pypi.org/project/mcp-for-blender/#history)及[空的 GitHub Releases 页面](https://github.com/ahujasid/mcp-for-blender/releases)。

## 2. MCP 的实际前提与风险

社区 MCP 需要本地 Blender、Python 3.10+ 和 uv 等运行环境，不能靠安装一份 Skill 文档就获得建模能力。它能够执行 Blender Python，连接应限制在本机；上游说明远程接口没有认证与加密，不能直接暴露到公网。[维护者说明](https://github.com/ahujasid/mcp-for-blender#limitations--security-considerations)

上游默认采集匿名工具使用统计，内容采集另需同意；可通过 `DISABLE_TELEMETRY=true` 关闭全部遥测。若后续安装，应明确配置这项设置并先在测试场景验证。这里记录的是上游行为，不代表已审计全部代码或已在本机完成验证。[遥测说明](https://github.com/ahujasid/mcp-for-blender#telemetry-control)

## 3. 本项目采用顺序

当前资料是两个不同年份和视角的规划项目效果图，以及总平面图等附件。资料足以支持有来源的图片热点，但仍缺统一现状测绘、可靠建筑高度、楼层平面、真实设备位置和可用模型文件。因此，不能从这些图直接推断准确校园三维结构，也不能生成虚构校园后称为浙江交院真实数字孪生。

1. **本期：继续图片地图。** 保留真实规划图片、独立 `image_id`、0—1 归一化坐标和待核实标识，优先保证设备、风险、巡检、任务回返等交互。
2. **取得单栋可信模型后：考虑 Three.js。** 对接 glTF/GLB，保持业务建筑 ID、设备 ID 与对象名称稳定对应；先验证体积、点击定位与页面性能。
3. **取得地理配准的校区数据后：考虑 CesiumJS。** 校验坐标系、校区范围、模型与影像的授权及更新日期，再展示地理空间关系。
4. **需要资产加工时：考虑 Blender 与 MCP。** MCP 用于辅助编辑、检查和批处理，不能替代测绘、BIM 或校方确认；任何简化模型都要标清来源及 DEMO 范围。

## 4. 上游参考与本地实现的区别

本次参考上游的 glTF 资产加载、地理空间坐标与资产工具分层思路，核对了版本、许可证和接入代价。上述三项工具目前都没有成为本项目运行依赖。

Day 2 的图片/SVG 共用坐标变换、建筑和设备热点、按路线长度插值、统一 SQLite 演示数据、巡检状态机及工作台任务回返，均针对当前项目自行实现。工具调研不构成“已接入真实三维模型、已完成真实地理配准或已具备自动建模”的交付声明。
