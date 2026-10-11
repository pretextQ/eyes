# 干净部署、独立接入与权限验收

日期：2026-10-11（Asia/Shanghai），开始基线 `9281a076d0d1a01dae7ae9a136375475cb891fb1`，分支 `main`。本轮只推进干净部署、独立接入和权限，不重做完整证据备份恢复，不扩展新功能。依据 AGENT、README、PLAN、Compose/Dockerfile、Agent/观测接入说明及[已有完整恢复记录](backup-release-review-20261011.md)。

## 干净控制平台与目录权限修复

Docker Engine 29.8.2。新项目 `eyes-clean-20261011`，API 18064、Web 18086、PostgreSQL 55446；独立网络、新数据库/证据卷。启动前保存原容器和卷清单，未启动、覆盖或删除原服务及数据。新私有材料位于 Git 忽略的 `data/clean-deployment-20261011/`，Windows 目录 ACL 仅当前用户。环境、令牌、构建/运行日志与响应均不提交。

实际执行仓库 `deploy/compose.yaml`，使用独立环境文件及 `-p`，`build --no-cache --pull`；没有用已有 `eyes-mewcode:local` 镜像。后端 Dockerfile 用 Python 3.14.7、uv 0.12.2，实际运行 `uv sync --frozen --no-dev`；前端 Node 24 的空构建层实际运行 `npm ci`、`npm run build`。首次构建与 `up --no-build -d` 均退出 0。PostgreSQL 18.6 健康，migrate 退出 0，API 健康、Scheduler 持续运行、Web 首页及代理 readiness 为 200。宿主机 `alembic heads` 和新服务 `alembic current` 都为 `0005_reconciliation`；新库 `alembic check` 通过。执行首次 bootstrap 创建两个独立真实项目，并分别签发 read 凭据；没有恢复旧库或预置业务数据。

**明确部署缺陷及最小修复**：初始 API 身份为 UID/GID 10001，但镜像初始化的 `/app/data/artifacts` 为 `10001:10001 / 0755`，UID 65534 实际可以列目录。`deploy/Dockerfile` 只追加 `chmod 0700 /app/data/artifacts`，保持原运行身份和产物发布逻辑。重新无缓存构建控制镜像，采用新的 `eyes-clean-20261011_artifacts-private` 卷启动；原初始空卷保留，没有在旧卷上隐藏失败或放宽权限。新目录实际为 `10001:10001 / 0700`，UID 65534 列目录返回 permission denied / 退出 2。API readiness=200，服务用户 `eyes-ops audit` 为 ok（当前尚无业务产物）。README 明确新卷权限及已有卷不自动交接的边界。真实产物授权下载在后续接入阶段验证，空卷 audit 不代替它。

前端干净安装报告 7 项 high：链路来自 devDependency `shadcn` 及 registry/ts-morph/glob/braces。保留实际 `npm audit --json` 和锁文件摘要，未运行 audit fix 或升级依赖。仍需按实际漏洞条件核实影响，不能因构建成功宣称依赖安全。

独立 Agent/Runner 最小真实闭环、完整权限矩阵及产物下载仍在本轮继续验证；本节只记录已完成的部署与权限修复，不宣称全部 M4 通过。
