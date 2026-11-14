# Eyes

[![CI](https://github.com/pretextQ/eyes/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/pretextQ/eyes/actions/workflows/ci.yml)

Eyes 是面向单团队自托管的 AI Agent 评测与执行观测平台。可以用自己的测试集和评分口径批量执行 Agent，逐条审阅结果、事件和产物，并生成可追溯的回归报告。也可以在 Agent 日常运行时独立收集观测事件。

**当前版本 `0.1.0`，数据库迁移头 `0008_work_indexes`。** 已验收的部署环境为 Windows 上的 Docker Desktop Linux 容器，支持按需启动和停止。[2026-11-14 交付审核](docs/Review/2026-11-14-release-readiness.md)

## 快速开始

### Docker Compose

启动 Docker Desktop 并确认使用 Linux 容器。以下命令在仓库根目录的 PowerShell 7 中运行。已有部署升级前，先按[升级与备份](docs/platform.md#升级与兼容)留存数据库和证据卷。

**1. 准备配置。** 首次部署时，从示例复制配置，并为 `POSTGRES_PASSWORD` 生成十六进制密码。

```powershell
if (!(Test-Path -LiteralPath 'deploy/.env')) {
    Copy-Item -LiteralPath 'deploy/.env.example' -Destination 'deploy/.env'
    $postgresPassword = [Convert]::ToHexString([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
    (Get-Content -LiteralPath 'deploy/.env' -Raw).Replace('replace-with-a-generated-hex-password', $postgresPassword) |
        Set-Content -LiteralPath 'deploy/.env' -NoNewline
}
```

已有部署沿用现有配置和密码。若此前已手动复制示例，请先在 `deploy/.env` 替换密码占位值。数据库、API 或 Web 端口被占用时，在同一文件中设置 `EYES_POSTGRES_PORT`、`EYES_API_PORT` 或 `EYES_WEB_PORT`。

**2. 构建并启动。** Compose 启动 PostgreSQL、执行数据库迁移，再启动 API、Scheduler 和 Web 控制台。数据库和证据分别写入持久卷。

```powershell
docker compose --env-file deploy/.env -f deploy/compose.yaml up --build --wait
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health/ready'
```

就绪响应应包含 `status: ready` 和 `database_revision: 0008_work_indexes`。API 端口改过时，使用实际端口。

**3. 创建项目并连接。** 只在需要新项目时运行以下命令。保存输出中的项目 ID 与管理令牌，打开 Web 控制台，在 **连接设置** 填入令牌。日常浏览可以使用独立的只读令牌。[令牌管理](docs/backend.md#令牌及项目范围)

```powershell
docker compose --env-file deploy/.env -f deploy/compose.yaml exec api eyes-admin bootstrap --name default
```

| 入口 | 默认地址 |
| --- | --- |
| Web 控制台 | [http://127.0.0.1:8080](http://127.0.0.1:8080/) |
| 控制 API 就绪检查 | [http://127.0.0.1:8000/health/ready](http://127.0.0.1:8000/health/ready) |
| API 文档与 OpenAPI | [Swagger UI](http://127.0.0.1:8000/docs) · [OpenAPI JSON](http://127.0.0.1:8000/openapi.json) |

Compose 默认将端口绑定到本机回环地址。API 文档通过控制 API 端口直连。浏览器项目令牌保存在页面内存，刷新后需重新连接。

## 选择使用路径

### 主动评测

1. 发布要评测的 Agent 版本，导入 JSONL 测试集，配置规则评分器或可信 Python 评分器。
2. 按目标和评分器配置并启动独立 Runner。Runner 使用限项目、目标版本和工作类型的令牌。Compose 负责控制端，Runner 随目标接入单独配置。
3. 从 **实验** 创建一次评测，或从 **多 Agent 批次** 并行验证多个目标。在用例详情核对执行状态、评分、事件与产物。
4. 使用相同测试集与评分口径运行基线和候选，在 **回归报告** 创建固定报告。CLI 可用 `eyes gate REPORT_UUID` 将报告结论接入 CI。

实验冻结目标、测试集、评分器和执行配置。重新评分生成独立历史记录，固定报告继续引用创建时选定的评分和证据。[Agent 与 Runner 接入](docs/agent-integration.md) · [MewCode 实例](integrations/mewcode/README.md) · [回归和 CLI](docs/platform.md#1-固定回归报告与-ci)

### 被动观测

1. 在 **Agent 观测 → 接入 Agent → 远程 Agent 接入** 使用管理令牌创建来源。
2. 将来源令牌和 Agent 运行环境可达的上报地址配置到 exporter。
3. 在 Agent 中照常运行任务，用项目令牌打开观测详情，查看上报的模型调用、工具事件和链路。

该路径只需控制端和 exporter。来源令牌用于上报，项目令牌用于读取。页面展示实际收到的事件及其完整性。[观测接入](docs/observation.md#启动与接入) · [trae 实际验收](docs/observation-trae-acceptance-20261012.md)

## 运行与维护

停止前先核对活动及 `unknown` 工作，按目标能力等待或确认停止，并关闭独立 Runner 与其他写入端。再次启动时沿用原 Compose 项目和数据卷。

```powershell
docker compose --env-file deploy/.env -f deploy/compose.yaml stop
docker compose --env-file deploy/.env -f deploy/compose.yaml up --wait
```

使用 **运行状态** 查看队列、Runner 心跳和当前容量告警。备份同时保存数据库和证据卷，恢复使用独立空目标并核对证据摘要。完整证据和观测正文的按年龄清理默认关闭。[备份与恢复](docs/platform.md#compose-命名卷的停写备份与恢复) · [容量保护](docs/platform.md#容量保护与当前告警) · [观测保留](docs/observation.md#观测保留与清理)

### 源码开发

后端和 Runner 使用 Python 3.14+、FastAPI、SQLAlchemy、PostgreSQL，Web 使用 React、TypeScript 和 Vite。Windows 上，API 与 Runner 使用 Docker Linux 容器，前端、CLI 和静态检查可原生运行。

```powershell
uv sync --frozen
uv run --no-sync ruff check src migrations integrations
uv run --no-sync ruff format --check src migrations integrations

Set-Location frontend
npm ci
npm run lint
npm run format:check
npm run build
```

前端要求 Node.js 22.12+，CI 与容器使用 Node.js 24。设置 `EYES_API_PROXY_TARGET` 可为本地 Vite 指定控制 API 地址。[后端开发](docs/backend.md#本机运行) · [前端开发](docs/frontend.md#本地启动) · [CI 工作流](.github/workflows/ci.yml) · [开发约定](AGENT.md)

## 交付验证

| 范围 | 最新证据 |
| --- | --- |
| 部署、权限与停启 | 隔离 Compose 从空库迁移至 `0008`。已复验 API 与 Web 就绪、指定权限及重启后持久数据一致性。[交付审核](docs/Review/2026-11-14-release-readiness.md) |
| 历史备份恢复 | 从 `0007` 备份恢复并升级至 `0008`，核对 27 份产物、49 份证据清单和 16 条评分。[交付审核](docs/Review/2026-11-14-release-readiness.md#本轮核对结果) |
| 真实版本回归 | MewCode 两个真实版本在同一批 3 个任务上均通过，3 项结果无变化。已复查固定报告、评分与产物。[回归记录](docs/mewcode-regression-20261111.md) |
| 观测与审阅 | 已有 trae 实际上报验收。最新浏览器复验覆盖窄屏、迟到补传和历史评分证据定位。[观测验收](docs/observation-trae-acceptance-20261012.md) · [交付审核](docs/Review/2026-11-14-release-readiness.md#设计待办审核) |

投入使用时，用实际项目、Agent 和权限配置完成一次对应路径的首单核对。原始 M0～M4 仍按各自证据范围验收，完整故障矩阵、真实版本改善或退化及长期容量仍有待验证边界。[开发计划](docs/PLAN.md#m0m4-验收状态) · [完整文档索引](docs/README.md)
