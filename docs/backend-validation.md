# 后端基础版本验证记录

记录日期：2026-10-01。项目尚无 Git 仓库，本次未生成提交或发布版本。应用包版本 `0.1.0`；迁移版本 `0001_control_plane`。

环境为 macOS Apple Silicon、CPython 3.14.7。依赖安装到项目 `.venv`，uv 缓存位于可写临时目录。未新增或修改仓库测试，也未生成测试脚手架、断言或模拟目标。

## 已执行

| 检查 | 命令或操作 | 结果 |
| --- | --- | --- |
| Python 依赖 | `UV_CACHE_DIR=/private/tmp/eyes-uv-cache uv sync` | 解析、安装并生成 uv.lock 成功 |
| 静态检查 | `.venv/bin/ruff check src migrations` | 通过 |
| 格式检查 | `.venv/bin/ruff format --check src migrations` | 通过 |
| 语法编译 | `.venv/bin/python -m compileall -q src migrations` | 通过 |
| OpenAPI | 导入 create_app 并生成 OpenAPI | 28 个路径，成功 |
| 迁移升级 SQL | `.venv/bin/alembic upgrade head --sql` | 生成 PostgreSQL DDL 成功 |
| 迁移回滚 SQL | `.venv/bin/alembic downgrade 0001_control_plane:base --sql` | 生成回滚 DDL 成功 |
| 安装包 | `UV_CACHE_DIR=/private/tmp/eyes-uv-cache uv build` | sdist/wheel 构建成功 |
| Compose 配置 | `POSTGRES_PASSWORD=compose-validation-placeholder docker compose -f deploy/compose.yaml config --quiet` | 配置校验通过 |
| API 实际启动 | `.venv/bin/uvicorn eyes.server.api.app:create_app --factory --host 127.0.0.1 --port 8042` | 完成应用 startup 并监听 |

本轮锁定的主要版本：FastAPI 0.142.2、Pydantic 2.13.5、SQLAlchemy 2.0.54、psycopg 3.3.6、Alembic 1.20.0、OpenTelemetry SDK 1.45.0。完整版本以 uv.lock 为准。

实际 HTTP 请求及响应主体：

```text
GET /health/live
HTTP/1.1 200 OK
{"status":"ok"}

GET /v1/experiments   [无 Bearer 令牌]
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer
{"schema_version":"1.0","error":{"code":"authentication_required","message":"Bearer token required","details":null}}

GET /health/ready     [数据库未运行]
HTTP/1.1 503 Service Unavailable
{"schema_version":"1.0","error":{"code":"migration_required","message":"database is unavailable or not migrated","details":null}}
```

响应均包含 X-Eyes-Trace-Id。这里只验证基础 HTTP 行为与实际 API 进程启动，未访问成功的业务数据库事务。

最终源码变更后重新启动并复查了上述三项 HTTP 请求，结果一致。重启的首次操作因原验证进程仍占用 8042 端口而返回 `Errno 48: address already in use`；通过原终端会话的 Ctrl-C 关闭后重新启动成功。验证结束后已关闭 API 验证进程。

## 环境限制与未执行项

本机 Docker CLI 可用，但守护进程未运行：

```text
failed to connect to the docker API at unix:///Users/<user>/.docker/run/docker.sock
connect: no such file or directory
```

本机未安装 PostgreSQL 命令。为尝试真实数据库验证，下载 Zonky 的 PostgreSQL 18.3.0 Darwin ARM64 发行包到 `/private/tmp`。原生通用二进制包含 ARM64 架构；未安装到系统目录。初始化命令为：

```sh
/private/tmp/eyes-pg-bin/bin/initdb -D /private/tmp/eyes-pg-data -U eyes \
  --auth=trust --encoding=UTF8 --locale=C
```

初始化失败：

```text
FATAL: could not create shared memory segment: Operation not permitted
DETAIL: Failed system call was shmget(key=14095643, size=56, 03600).
child process exited with exit code 1
initdb: removing data directory "/private/tmp/eyes-pg-data"
```

增加 `-c shared_memory_type=mmap -c dynamic_shared_memory_type=mmap` 后，仍因 shmget 被当前执行沙箱拒绝而失败。停止数据库启动尝试，未使用 SQLite 替代，也未更改 macOS 设置或启动 Docker GUI。

因此尚未验证：数据库迁移实际应用/回滚、不可变触发器、业务接口持久化、认证令牌生命周期、并发领取与限额、幂等冲突、事件去重、产物上传、取消/租约恢复及重新评分。Compose 镜像构建和容器运行也未执行。独立 Runner 与两种真实 Agent 接入还未实现或验收。

M0 状态为契约和控制端基础实现中，尚未与两个真实目标逐项核对；M1/M2/M3/M4 均未验收。后续运行必须追加实际命令、原始返回和失败记录，不能把本次静态检查替换为运行验证。

## 2026-10-02：通用 Agent 接入实现

本次新增宿主机 Runner、通用 HTTP 与本地 Python 适配器、可信规则/Python 评分进程、SDK 事件及产物采集、本地 journal/outbox 和接入文档。上面的 2026-10-01 状态是当时快照；其中“执行组件未实现”已经由本节更新。

用户明确要求先完成 HTTP 和本地接入功能，暂不接入两个真实 Agent。未调用 Zeta、Deta 或其他目标项目，未启动模拟目标，未新增或修改测试文件、测试用例、断言、fixtures 或 mocks。本次仍没有 Git 提交或发布；包版本保持 0.1.0，数据库迁移保持 0001_control_plane。

### 已执行检查

| 检查 | 命令或操作 | 结果 |
| --- | --- | --- |
| 固定依赖安装 | `UV_CACHE_DIR=/private/tmp/eyes-uv-cache uv sync --frozen` | 通过；新增 HTTPX 0.28.1，uv.lock 已更新 |
| 静态检查 | `.venv/bin/ruff check src migrations` | 通过 |
| 格式检查 | `.venv/bin/ruff format --check src migrations` | 51 个 Python 文件通过 |
| Python 编译 | `.venv/bin/python -m compileall -q src migrations` | 通过 |
| Runner CLI | `.venv/bin/eyes-runner --help` | run/plugins/status 命令及参数正常显示 |
| 插件检查 | `.venv/bin/eyes-runner --config deploy/runner.example.toml plugins` | 读取 TOML、规范化 HTTP origin，并在独立解释器读取 rules 实现摘要成功；模板未配置真实 Python Agent |
| 本地状态 CLI | `.venv/bin/eyes-runner --config deploy/runner.example.toml status` | pending/rejected/retained/quarantined 均为 0；未连接控制端 |
| OpenAPI | create_app 生成 OpenAPI | 28 个路径成功生成，新契约字段进入 schema |
| 迁移升级/回滚 SQL | `.venv/bin/alembic upgrade head --sql` 与 `.venv/bin/alembic downgrade 0001_control_plane:base --sql` | PostgreSQL DDL 生成成功；未应用到数据库 |
| Compose 配置 | `POSTGRES_PASSWORD=compose-validation-placeholder docker compose -f deploy/compose.yaml config --quiet` | 通过；未启动容器 |
| 安装包 | `UV_CACHE_DIR=/private/tmp/eyes-uv-cache uv build` | 最终源码生成 sdist 与 wheel 成功 |
| 客户端依赖边界 | 使用 Python 3.14 AST 检查 runner/adapters/scorers/sdk/contracts 的 import | 无 eyes.server、SQLAlchemy、psycopg 或 Alembic 导入 |
| 本地文档链接 | 检查 README、backend、architecture、agent-integration 中的相对链接 | 无缺失目标 |

最终 rules 源码摘要（之后修改该文件需重新发布评分器版本）：

```text
bf889c492b4a658f6cf2921c5b7cb63b949bbee598ccc453137a52bdccc4da97
```

过程中先运行 Ruff，发现新文件的导入顺序及长行问题；格式化并修正后通过。依赖边界检查首次误用了系统 `python3`（3.13）解析 Ruff 按 3.14 格式输出的多异常 except 语法，返回 `SyntaxError: multiple exception types must be parenthesized`；改用项目 `.venv/bin/python`（3.14）后完成检查。项目 Python 要求没有降低。

### 本次检查的边界

本节证明源码静态检查、编译、安装包生成和 CLI 入口/内置插件检查通过。未实际执行 Agent，未在控制 API 领取任务、运行评分或上传证据，不能视为 HTTP/Python 执行闭环、取消、隔离或恢复的运行证明。

PostgreSQL 与 Docker 的可用环境仍受前一节所述限制；本次未重复尝试绕过共享内存限制，也未用 SQLite 替代 PostgreSQL。实际迁移、业务持久化、产物登记重传、并发配额、租约、未知结果协调、故障恢复和两个真实目标的验收仍待后续运行。M0/M1/M2 未验收；回归比较、质量门槛与产品界面不属于本次已完成范围。

可复用的启动和接入步骤见 [Agent 接入文档](agent-integration.md)，本机配置模板见 [runner.example.toml](../deploy/runner.example.toml)。

## 2026-10-02：代码审查的六项修复

根据审查结果修复：证据重试阻塞完成上报、评分大输入超过领取/进程消息上限、Runner 缺少别名/能力/origin 匹配、评分截止后诊断被拒绝、常用敏感头漏检，以及前端用例对话框无法跟随首个 Attempt。具体协议、配置及升级边界见 [接入文档](agent-integration.md)。未新增或修改测试、fixtures、mocks、断言或模拟目标；数据库迁移仍为 `0001_control_plane`。

| 检查 | 命令或操作 | 结果 |
| --- | --- | --- |
| 后端静态/格式检查 | `.venv/bin/ruff check src migrations`、`.venv/bin/ruff format --check src migrations` | 通过，51 个 Python 文件格式通过 |
| Python 编译 | `.venv/bin/python -m compileall -q src migrations` | 通过 |
| 前端检查 | `npm run lint`、`npm run build`、`npm run format:check` | 通过；build 包含 TypeScript 检查 |
| Runner 插件与状态 | `.venv/bin/eyes-runner --config deploy/runner.example.toml plugins` 和 `status` | 模板读取及独立解释器 rules 摘要成功；四项本地状态计数为 0，未领取任务 |
| Compose 配置 | `POSTGRES_PASSWORD=compose-validation-placeholder docker compose -f deploy/compose.yaml config --quiet` | 通过，API/scheduler 共用新增配置；未启动容器 |
| 重启 API | 关闭原终端 API 后运行 `.venv/bin/eyes-server` | startup 成功，监听 `127.0.0.1:8000` |
| OpenAPI | 通过 Vite 代理读取 `/openapi.json` | 29 个路径，含评分输入接口；注册字段与 `completed_at` 已更新 |
| 真实 HTTP | `/api/health/live`、`/api/v1/experiments`、无令牌的 `POST /api/v1/work/{id}/score-input`、`/api/health/ready` | 依次为 200、401、401、503（migration_required） |
| Chrome 浏览器 | 刷新实验工作台，打开/关闭连接弹窗，读取控制台错误 | 未连接视图正常，空令牌按钮禁用，无 warn/error；前端与 API 保持运行 |

首次前端格式检查指出 Experiment.tsx 的排版问题，使用已有 Prettier 仅格式化该文件后通过。六项改动的调用链、共享字段表和截止/提交窗口已作源码复核；没有以构造的业务数据或内联断言代替运行验证。

PostgreSQL 仍无可用连接。以上证明检查、实际 API 启动、认证入口和未连接页面可用，不能证明多 Runner 的任务分配、超过 1 MiB 的真实评分轨迹、证据接口失败期间的结果入库、超时诊断持久化或前端队列到执行的实时变化。这些数据库与真实 Agent 场景仍待可用环境验证，M1/M2 未验收。

## 2026-10-03：回归、证据等待与运维

本轮迁移升级到 `0002_platform`，新增持久化回归报告和 CI/运维 CLI、服务端证据等待、评分取消/重试、证据过期清理及备份恢复。实际验证已覆盖独立 PostgreSQL 17 副本上的迁移、报告和排队取消，以及全新 PostgreSQL 18.6 Compose 部署、数据库备份恢复。详细命令、结果、修复和未验证范围见 [平台验证记录](platform-validation.md)，使用说明见 [平台说明](platform.md)。历史章节中数据库不可用、回归/CLI/运维未实现为当时状态。
