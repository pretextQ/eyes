# Eyes 缺陷修复验证记录（2026-10-17）

范围：`docs/fix-plan-20261017.md` 中 FIX-01～FIX-08 的整体验证。基线 `7f998a6`，修复与验证提交从 `286d4f6` 起（未推送）。本记录只证明本轮修复与既有静态/冒烟检查，不新增产品验收结论，也不改变 M0～M4 的历史状态。

## 环境

| 项 | 实测值 |
| --- | --- |
| 宿主机 | Windows，PowerShell 7 |
| Python / uv | CPython 3.14.4 / uv 0.11.7 |
| Node / npm | v22.14.0 / 10.9.2 |
| PostgreSQL | 15.17，隔离临时集群（数据目录在 `%TEMP%\eyes-fix-pg-20261017`，端口 55499，trust 认证） |
| 容器 | 首轮未使用；第二轮启动 Docker Desktop（Server 29.8.2），构建 `eyes-fix-20261017:local` 并运行 Linux 容器 |
| 前端依赖 | 现有 `frontend/node_modules`（`package-lock.json` 锁定） |

## 结果总览

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| Python 规范 | `uv run --no-sync ruff check src migrations` | 通过（All checks passed） |
| Python 格式 | `uv run --no-sync ruff format --check src migrations` | 通过（88 files already formatted） |
| 空白/冲突 | `git diff --check` | 通过（无输出） |
| 控制契约幂等 | 重新导出 `python -m eyes.contracts.schema` 并比对 | 逐字节一致（exit 0） |
| Agent 协议幂等 | 重新导出 `python -m eyes.contracts.agent_protocol` 并比对 | 逐字节一致（exit 0） |
| 迁移升级 | `alembic upgrade head` | 通过（0001→0007） |
| 迁移降级 | `alembic downgrade base` | 通过（0007→base） |
| 迁移重放 | 再次 `alembic upgrade head` | 通过 |
| 模型漂移 | `alembic check` | No new upgrade operations detected |
| 初始化 | `eyes-admin bootstrap --name fix-smoke` | 通过（只记录 project/credential id，未输出令牌） |
| 前端 lint | `npm run lint` | 通过（exit 0） |
| 前端格式 | `npm run format:check` | 通过（All matched files use Prettier code style） |
| 前端构建 | `npm run build`（含 `tsc -b`） | 通过（built in 17.04s） |
| API 冒烟（Windows） | `python data/fix-verification-20261017/smoke.py` | 43/43 通过（exit 0） |
| Docker 镜像构建 | `docker build -f deploy/Dockerfile -t eyes-fix-20261017:local .` | 成功（432MB） |
| 容器内迁移 | upgrade → downgrade base → upgrade → `alembic check` | 全部通过（PostgreSQL 18.6） |
| 容器内 API 冒烟 | 同一脚本，`EYES_SMOKE_REAL_STORE=1` | 43/43 通过（真实 POSIX 证据存储） |

## API 冒烟覆盖

冒烟在本机 Python 进程中直接构造 `create_app`，连接临时数据库；证据存储替换为临时目录实现（Windows 无法对目录执行 POSIX fsync，详见“限制”）。覆盖：

1. 健康检查：`/health/live`、`/health/ready`（迁移版本与存储探测）。
2. 认证与权限：无令牌 401、read 令牌发布目标 403。
3. 目录：发布 python 目标、发布 rules 评分器、导入单用例 JSONL。
4. 实验一：创建（幂等键）→ Runner 注册/领取 → preparing/running → 事件上报 → 成功结果 → 评分领取 → score-input 校验 → 评分完成。
5. 汇总：计划 1、执行成功 1、有效评分通过 1。
6. 实验二：执行 + 产物登记/上传/下载（字节一致）+ 评分引用产物。
7. 比较：同评分器配对，门禁 `pass`，报告内容可读。
8. 取消：排队实验取消，`cancellation-audits` 记录 `processed`。
9. 其他：重新评分 201、容量测量 2 项、`/v1/contracts` 含 `CancellationRequest/ReconciliationEvidence/RecoveryEventSubmission`、无窗口的 legacy 头返回 422。

## Docker / Linux 复验（第二轮）

首轮在 Windows 本机完成；按用户要求启动 Docker Desktop 后，用当前 HEAD 重新构建镜像并在隔离容器中复跑。

| 步骤 | 结果 |
| --- | --- |
| 构建 | `docker build -f deploy/Dockerfile -t eyes-fix-20261017:local .` 成功（Python 3.14.7-slim + uv 0.12.2） |
| 数据库 | `postgres:18.6` 新容器 + 新命名卷，未复用任何历史卷 |
| 迁移 | 容器内 `alembic upgrade head` → `downgrade base` → `upgrade head` → `alembic check` 全部通过 |
| 初始化 | `eyes-admin bootstrap` 成功（令牌只写入私有临时文件，验证后删除） |
| 服务 | API + Scheduler 容器启动；`/health/ready` 返回 `0007_cancellation_audit`；Scheduler 每 5 秒输出 sweep |
| 证据存储 | 容器内 `/app/data/artifacts` 为 `eyes:eyes`、`0700`，真实 `LocalArtifactStore`（非 Windows 桩） |
| 业务冒烟 | `smoke.py` 以 `EYES_SMOKE_REAL_STORE=1` 在容器内运行，43/43 通过 |
| HTTP 读 | 无令牌 401、manage 200、`/v1/contracts` 200、`/v1/operations/capacity` 200、不存在产物 404 |
| HTTP 写 | 通过真实 HTTP 发布目标/评分器、导入数据集、创建实验、列表、取消并写入审计（`processed`） |

清理：只停止并删除本轮创建的 `eyes-fix-20261017-{api,scheduler,pg}` 容器和网络；保留卷 `eyes-fix-20261017-pg` / `eyes-fix-20261017-artifacts` 与镜像供复核，未启动、停止或修改任何既有容器/卷。

## 与修复项的对应

| FIX | 验证方式 |
| --- | --- |
| FIX-01 | 契约导出幂等 + `/v1/contracts` 冒烟包含三个新增模型 |
| FIX-02 | 全仓检索现值 `0005` 表述为空；文档链接与 README/PLAN 入口提交 |
| FIX-03 | `tsc -b`、`npm run build`；非法日期分支代码审阅 |
| FIX-04 | 构建通过；下载路径代码审阅（无浏览器自动化） |
| FIX-05 | 构建通过；401 回调路径代码审阅（冒烟覆盖了 401 响应，但未驱动浏览器断开流程） |
| FIX-06 | `tsc -b` 与后端契约逐字段对照 |
| FIX-07 | `tsc -b`；分页上限代码审阅 |
| FIX-08 | 全仓无 `eyebrow`；`tsc -b` 与构建通过 |

## 限制与未覆盖

- **没有新增仓库测试**：按 `AGENT.md` 的约定，本轮只运行既有检查和临时冒烟脚本；冒烟脚本位于被 Git 忽略的 `data/fix-verification-20261017/`，不属于测试套件，也不进入 CI。
- **API 冒烟仍不是完整部署验收**：Windows 轮使用 `TestClient` + 临时证据实现；Docker 轮已覆盖真实 POSIX 证据存储、PostgreSQL 18.6、真实 uvicorn API/Scheduler，但仍未覆盖 nginx、Compose 全栈、Runner/Agent 容器与浏览器。
- **数据库版本**：Windows 轮为 PostgreSQL 15.17；Docker 轮为 `postgres:18.6`，迁移与冒烟均在 18 上通过；未在 18 上重跑前端或浏览器检查。
- **前端行为验证有限**：本机无浏览器自动化，FIX-03/04/05 只做类型检查、构建和代码审阅；未做真实点击下载或令牌撤销后的页面截图。
- **冒烟脚本迭代**：首次执行在创建比较报告时失败，原因是测试夹具的 `scorer_pairs` 缺少嵌套 `schema_version`（公共契约要求），不是产品代码缺陷；补齐夹具后完整重跑通过。Docker HTTP 写入首次失败，是因为 PowerShell `ConvertTo-Json` 把 JSONL 展开成多行，服务端按行校验后正确返回 `invalid_dataset`；改用单行 JSONL 后通过。两次失败均保留说明，未删除。
- **测试环境操作**：本机 `pg_ctl start` 会因 postgres 继承输出句柄而不返回，改用 `Start-Process postgres.exe` 启动；这是本机测试脚本问题，不是产品缺陷。临时集群已停止，数据目录保留供复核。

## 复现

```powershell
# 1. 静态检查
uv run --no-sync ruff check src migrations
uv run --no-sync ruff format --check src migrations

# 2. 临时 PostgreSQL（示例，需 PostgreSQL 15+ 客户端）
$PG = "D:\software\tools\PostgreSQL\15\bin"
& "$PG\initdb.exe" -D $env:TEMP\eyes-fix-pg -U eyes --auth=trust -E UTF8 --locale=C
Start-Process "$PG\postgres.exe" -ArgumentList "-D", "$env:TEMP\eyes-fix-pg", "-p", "55499"
& "$PG\createdb.exe" -h 127.0.0.1 -p 55499 -U eyes eyes_fix
$env:EYES_DATABASE_URL = "postgresql+psycopg://eyes@127.0.0.1:55499/eyes_fix"
uv run --no-sync alembic upgrade head

# 3. 冒烟
$env:EYES_SMOKE_ARTIFACTS = "$PWD\data\fix-verification-20261017\artifacts"
uv run --no-sync python data\fix-verification-20261017\smoke.py

# 4. 前端
Set-Location frontend
npm run lint; npm run format:check; npm run build
```

## 结论

FIX-01～FIX-08 全部完成并分别提交；静态检查、契约导出、迁移升降级、前端 lint/format/build 与 43 项 API 冒烟全部通过。Docker/Linux 第二轮进一步用当前源码镜像、PostgreSQL 18.6、真实 POSIX 证据存储和真实 HTTP 复验通过。本记录提交后 `main` 领先 `origin/main` 11 个提交，**未推送**，等待用户审阅。
