# 天亨 SKYDOME 协作开发

## 双人协作入口

- [共同目标、暂定分工与协作约定](docs/team-collaboration.md)：两位共同负责人各自完整交付功能，再互相检查；包含与老板对齐的话术。
- [Iteration 01 协商初稿](docs/iteration-01.md)：基于当前代码核查的两项候选功能、接口草案、文件边界、逐项验收和暂定估时。
- [现有 Day 5 交付记录](docs/day5-final-delivery.md)：历史阶段能力与验收证据；最新基线结果见 Iteration 01。

上述分工和排期是待双方协商的建议，不代表已获老板批准或功能已经实现。

## 首次运行（Windows PowerShell）

安装 Git、Python 3.12 和 Node.js 24 后执行：

```powershell
git clone https://github.com/heqiucan/tianheng-skydome.git
Set-Location tianheng-skydome
py -3.12 -m venv .venv-day2
.\.venv-day2\Scripts\python.exe -m pip install -r backend\requirements.lock.txt
Set-Location frontend
npm ci
Set-Location ..
.\scripts\start.ps1
```

产品页面为 <http://127.0.0.1:5173>，接口文档为 <http://127.0.0.1:8000/docs>。端口已被占用时启动脚本会报错，不会终止其他项目。停止本地开发服务使用 `scripts/stop.ps1`。

启动时会自动创建模拟数据；不需要复制原开发机数据库，也不需要模型 API Key。运行数据默认保存在 `%LOCALAPPDATA%\TianqiongDemo`。不同机器各自维护数据库，不要通过 Git 或 OneDrive 同步正在使用的 SQLite 文件。如果同一台机器运行多个副本，为每个副本设置不同的 `TIANQIONG_DATA_DIR`，并自行协调端口。

## 分支与合并

`codex/team-collaboration` 用于协作计划和准备材料。本轮文档在该分支提交并推送；不直接修改 `main`。实际功能分别使用独立分支，通过后续 PR 互审后合入 `main`，不在准备分支混写两人的功能。

首轮建议分支为 `codex/task-follow-up-notes` 和 `codex/knowledge-category-search`，具体范围见上述计划。每人负责自己功能的前后端、测试和说明；由另一位共同负责人审查。PR 互审是协作约定，不表示仓库已配置强制审查规则。本轮准备工作不自动创建 PR 或 Issue。

开始开发前先确认工作区干净，再同步主分支，为每个改动创建独立分支：

```powershell
git status --short --branch
git switch main
git pull --ff-only origin main
git switch -c codex/describe-your-change
```

未提交的修改应先在原分支妥善处理；不要强制切换覆盖它们。两台电脑各用自己的 checkout。同机多个对话若共用目录，也共用当前分支；新建对话本身不会隔离代码，不能在同一 checkout 同时开发两个功能分支。

完成后只暂存本次修改的文件，检查差异并提交：

```powershell
git status
git diff
# 将下一行的路径替换为本次实际修改的文件。
git add path/to/changed-file
git diff --cached
git commit -m "Describe the change"
git push -u origin HEAD
```

在 GitHub 创建 Pull Request，说明解决的问题、页面行为变化和验证结果，由另一位同事检查后合并。公开仓库允许任何人拉取；直接推送需要接受仓库协作者邀请。没有写权限的贡献者也可以 fork 后提交 Pull Request。

## 提交前验证

在项目根目录执行：

```powershell
.\.venv-day2\Scripts\python.exe -m pytest --basetemp=.pytest-temp -p no:cacheprovider
Set-Location frontend
npm run build
node --test tests/*.test.mjs
Set-Location ..
```

按改动范围在浏览器检查实际操作。`/health` 仅表示服务存活，不能替代地图、证据查询或任务执行的验证。测试使用临时数据库；不要把运行数据库加入 Git。

## 代码与资料

- `frontend/src/`：Vue 界面、地图与任务交互。
- `backend/app/`：FastAPI、SQLite、证据快照、规则研判及模拟任务。
- `backend/tests/`、`frontend/tests/`、`scripts/tests/`：自动检查。
- `docs/`：阶段契约、验收记录和使用手册；历史记录描述对应阶段，以当前代码为准。
- `public/references/campus/`：产品运行使用的四张校园规划图片。

原始第三方设计截图、含人员信息的参考图和非必需素材归档保留在原开发机，不作为公开源码发布。学校图片是规划资料，不表示实时影像或真实三维模型；使用时保留来源，进一步分发和商用应单独核实权利。仓库公开本身不代表第三方素材获得开源授权。

`.env.example` 仅保留变量名。密钥、令牌、数据库、日志、个人路径和真实人员信息不要写入源码、截图或提交。

## 临时公网演示

Cloudflare 临时链接依赖原电脑在线，地址不会随 Git 仓库复制。日常开发使用本地启动方式即可。

`scripts/start-public-share.ps1` 依赖本机准备好的 `.runtime/share/site` 生产构建与 `.runtime/share/tools/cloudflared.exe`，这些内容不在 Git 中。分享构建需设置 `VITE_PROGRESS_TRANSPORT=poll`，以使用持久化事件轮询；分享服务使用独立数据库。普通 `scripts/stop.ps1` 只停止开发服务，分享进程应按 `.runtime/share/processes.json` 中的 PID、启动时间核对后单独停止。
