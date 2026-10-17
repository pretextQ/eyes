# Eyes 缺陷修复验证记录（2026-10-17）

范围：`docs/fix-plan-20261017.md` 中 FIX-01～FIX-08 的整体验证。基线 `7f998a6`，修复提交 `286d4f6`～`ce20c91`（9 个提交，未推送）。本记录只证明本轮修复与既有静态/冒烟检查，不新增产品验收结论，也不改变 M0～M4 的历史状态。

## 环境

| 项 | 实测值 |
| --- | --- |
| 宿主机 | Windows，PowerShell 7 |
| Python / uv | CPython 3.14.4 / uv 0.11.7 |
| Node / npm | v22.14.0 / 10.9.2 |
| PostgreSQL | 15.17，隔离临时集群（数据目录在 `%TEMP%\eyes-fix-pg-20261017`，端口 55499，trust 认证） |
| 容器 | Docker Desktop Linux 引擎未运行，本轮未使用 Compose |
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
| API 冒烟 | `python data/fix-verification-20261017/smoke.py` | 43/43 通过（exit 0） |

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
- **API 冒烟不是容器部署验收**：使用 FastAPI `TestClient` 与临时证据实现，未验证真实 uvicorn、nginx、Linux 卷权限、POSIX fsync 与 Docker Compose；这些仍以既有验收记录为准。
- **数据库版本差异**：本机临时集群为 PostgreSQL 15.17，CI 与部署目标为 18；本轮迁移与约束在 15 上通过，未在 18 上重跑。
- **前端行为验证有限**：本机无浏览器自动化，FIX-03/04/05 只做类型检查、构建和代码审阅；未做真实点击下载或令牌撤销后的页面截图。
- **冒烟脚本迭代**：首次执行在创建比较报告时失败，原因是测试夹具的 `scorer_pairs` 缺少嵌套 `schema_version`（公共契约要求），不是产品代码缺陷；补齐夹具后完整重跑通过。该失败保留在此说明，未删除。
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

FIX-01～FIX-08 全部完成并分别提交；静态检查、契约导出、迁移升降级、前端 lint/format/build 与 43 项 API 冒烟全部通过。当前 `main` 领先 `origin/main` 9 个提交，**未推送**，等待用户审阅。
