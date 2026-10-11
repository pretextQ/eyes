# 干净部署、独立接入与权限验收

日期：2026-10-11（Asia/Shanghai），开始基线 `9281a076d0d1a01dae7ae9a136375475cb891fb1`，分支 `main`。本轮只推进干净部署、独立接入和权限，不重做完整证据备份恢复，不扩展新功能。依据 AGENT、README、PLAN、Compose/Dockerfile、Agent/观测接入说明及[已有完整恢复记录](backup-release-review-20261011.md)。

## 干净控制平台与目录权限修复

Docker Engine 29.8.2。新项目 `eyes-clean-20261011`，API 18064、Web 18086、PostgreSQL 55446；独立网络、新数据库/证据卷。启动前保存原容器和卷清单，未启动、覆盖或删除原服务及数据。新私有材料位于 Git 忽略的 `data/clean-deployment-20261011/`，Windows 目录 ACL 仅当前用户。环境、令牌、构建/运行日志与响应均不提交。

实际执行仓库 `deploy/compose.yaml`，使用独立环境文件及 `-p`，`build --no-cache --pull`；没有用已有 `eyes-mewcode:local` 镜像。后端 Dockerfile 用 Python 3.14.7、uv 0.12.2，实际运行 `uv sync --frozen --no-dev`；前端 Node 24 的空构建层实际运行 `npm ci`、`npm run build`。首次构建与 `up --no-build -d` 均退出 0。PostgreSQL 18.6 健康，migrate 退出 0，API 健康、Scheduler 持续运行、Web 首页及代理 readiness 为 200。宿主机 `alembic heads` 和新服务 `alembic current` 都为 `0005_reconciliation`；新库 `alembic check` 通过。执行首次 bootstrap 创建两个独立真实项目，并分别签发 read 凭据；没有恢复旧库或预置业务数据。

**明确部署缺陷及最小修复**：初始 API 身份为 UID/GID 10001，但镜像初始化的 `/app/data/artifacts` 为 `10001:10001 / 0755`，UID 65534 实际可以列目录。`deploy/Dockerfile` 只追加 `chmod 0700 /app/data/artifacts`，保持原运行身份和产物发布逻辑。重新无缓存构建控制镜像，采用新的 `eyes-clean-20261011_artifacts-private` 卷启动；原初始空卷保留，没有在旧卷上隐藏失败或放宽权限。新目录实际为 `10001:10001 / 0700`，UID 65534 列目录返回 permission denied / 退出 2。API readiness=200，服务用户 `eyes-ops audit` 为 ok（当前尚无业务产物）。README 明确新卷权限及已有卷不自动交接的边界。真实产物授权下载在后续接入阶段验证，空卷 audit 不代替它。

前端干净安装报告 7 项 high：链路来自 devDependency `shadcn` 及 registry/ts-morph/glob/braces。保留实际 `npm audit --json` 和锁文件摘要，未运行 audit fix 或升级依赖。仍需按实际漏洞条件核实影响，不能因构建成功宣称依赖安全。

独立 Agent/Runner 最小真实闭环、完整权限矩阵及产物下载仍在本轮继续验证；本节只记录已完成的部署与权限修复，不宣称全部 M4 通过。

## 接入构建修复及已通过的检查

旧 `integrations/mewcode/Dockerfile` 没有 COPY Eyes 锁文件，使用浮动 uv 与非冻结 `uv pip install /app /opt/mewcode`；不能按仓库锁文件独立复现。最小调整为与控制镜像相同的 Python 3.14.7/uv 0.12.2，先 `uv sync --frozen --no-dev` 安装 Eyes，再导出外部 MewCode 非开发锁定依赖，安装当前环境缺少的包和 Agent。共享依赖不覆盖，最后 `uv pip check` 必须通过；不改外部源码或两份锁文件。同时将该镜像的新证据目录设为服务用户私有 `0700`。接入 README 增补干净构建、依赖边界、HTTP 服务必需变量、独立状态卷和分离 Runner 的实际步骤，避免固定旧脚本覆盖历史目录。

保留本轮第一次实现检查失败：依赖过滤误用了系统 Python 的 metadata，第一次镜像构建及 pip check 虽成功，逐项核对发现 14 个 Eyes 锁定包版本被替换。该镜像未运行 Agent 业务；改用 `/app/.venv/bin/python` 获取已冻结环境后，重新 `--no-cache --pull` 构建最终 `eyes-clean-mewcode-verified:20261011`，再核对共享包与干净控制镜像完全一致、pip check 通过，才启动业务。此前用于检查组合安装方法的独立私有镜像也保留，不作为文档构建证明。

实际 MewCode 提交 `3f104082b6c5ca53efe273630bf08f67f1fc3ff5`，运行容器全部 Python 源码与干净 Windows checkout 逐文件一致，实际源码映射摘要 `a007cfa9bcfb9d2f1051a154c6f64d2b42542fc83061d45ba046787d0b94e35d`。Git archive 的 LF 字节与 Windows checkout 行尾不同，不能将这项首次候选摘要比较不一致误报为加载缓存源码；随后明确比较实际 checkout 与运行字节。外部模型配置沿用已有无密钥参数和运行时密钥，未写入镜像或发布配置。外部 Agent 是真实执行目标，不是控制平台缓存运行镜像。

最终镜像已通过真实 HTTP 发现/能力读取，Agent 可加载、状态目录可写；干净控制镜像中的独立 Runner plugins 读取到原评分器文件摘要 `3e72cfd6a721cddd420f9d850cf79366545e886ec59b7377424c01fb0737d826`。新项目导入原完整三任务，签发限定目标与工作类型的凭据。真实闭环和权限矩阵的最终结果随后记录，不以构建/发现代替执行成功。
