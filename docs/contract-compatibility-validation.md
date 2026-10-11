# 旧 Runner/outbox 与冻结插件的实际兼容验收

2026-10-11（Asia/Shanghai），约 10:00～10:05。用户要求继续完成版本迁移遗留的旧 Runner/outbox 网络重传及插件兼容验收，中途先修复 Docker 启动故障。本次只验证以下真实组合，不扩展未知远端业务的故障矩阵，不调用 Agent/模型，不新增或修改仓库测试、用例、fixtures、mocks 或模拟 Agent。

## Docker 恢复与隔离

启动 Docker Desktop 4.72.0 时，实际日志报告 `dockerInference` Windows 临时套接字无法移除。退出崩溃进程后，将 `%LOCALAPPDATA%/Docker/run` 改名保留并重建；随后暴露同类 `docker-secrets-engine/engine.sock` 故障，确认该目录只有零字节套接字后，一并改名保留并重建两个临时目录。原 WSL 数据盘、设置、镜像、容器、命名卷未重置、删除或清理；没有 factory reset、prune 或 WSL unregister。

恢复后 Docker Client/Server 均为 29.4.2，Linux engine 正常，原 9 个容器、12 个镜像和命名卷仍在；原容器均停止，未启动旧 Runner/API/Agent。临时目录隔离属于本次启动恢复，未验证旧 Desktop 版本长期重启不复发；用户后续升级的选择不作为本次 Eyes 验收结果。

本次专用环境：

- 新私有目录 `data/runner-compat-validation-20261011/`，Windows ACL 限当前用户，不提交运行数据或凭据。
- 原 PostgreSQL 15 实例已停止，`pg_ctl status` 确认无服务运行。复制其冷态目录和真实 Artifact 目录到本次私有目录；仅移除副本中的旧 postmaster.pid，启动副本于 55441，原目录不启动、不修改。副本使用自身 WAL 恢复及 0004→0005 迁移，均只作用于副本。
- 专用 Docker 网络 `eyes-contract-compat`；新 API `eyes-contract-compat-api`，宿主仅映射 127.0.0.1:18054，Linux readiness 实际为 200/head=0005。
- 专用容器 `eyes-contract-compat-replay`、`eyes-contract-compat-old-runner`、`eyes-contract-compat-new-supervisor`。历史 Runner journal、凭据文件、冻结源码挂载只读；所有新状态和评分目录写入本次私有目录。凭据沿用冷态数据库副本中的对应身份，不将历史令牌发送到其他实例。
- 验收结束后停止全部本次容器及专用 PostgreSQL，保留记录、冷态副本和停止的容器供复查；Docker Desktop 保持可用。原数据库、原服务及任务状态未写入。

## 版本和真实材料

控制端、新 Supervisor：`3aa7e5012415da6495638614e12264ecf1bbdbc4`。旧 Runner/Worker/SDK：从已交付的 `6473c962d65255c83e4265fea12f6afce2f4932c` Git archive 取得原源码，在实际 Linux 安装路径加载，不用配置补版本来冒充旧实现。当前严格 API 没有开启 legacy schema 窗口。

沿用原真实运行镜像 `sha256:420dba75f4b41b95976e91e0d590cfc9d1fb3397a8a64b39c1c21ed167ceca2a`，Linux CPython 3.14.7 和其实际依赖；没有安装或升级依赖，不声称该历史镜像采用完整当前锁文件。新 Supervisor 与旧 Worker 分别使用不同 venv/模块路径；运行时实际核对新 Contract 的 version_required=true，旧 Contract 的 version_required=false。

冻结评分器是原 `integrations/deta/scorer.py`，摘要仍为 `11badc0d2397a20b51d7c41fcdbb246b68ca2dca600646b2a6f95ccd234a89b6`，没有把当前修改后的评分源码或摘要覆盖历史 ScorerVersion。它通过原有四项检查实际执行已冻结的真实代码产物。

材料来自已完成 MewCode HTTP 实验 `e93b6f02-0d9e-4a0d-abba-47e48e305847` 的三个成功 Attempt，以及真实保留的 6 份 completion journal（3 执行、3 评分）。新环境的三个 CaseRun、Attempt、远端 run 身份和业务输入沿用冷态副本，不创建新的业务 Attempt 或远端执行。评分通过公共 rescore 创建新 ScoreRun，绑定原证据清单；历史 ScoreRun 保留。

## 旧 outbox 的真实网络中断和恢复

将 6 份原 journal 的原 body、work_id、lease token、Runner 身份及结果放入专用旧版 Outbox，保留原目录只读。使用旧版 ControlClient/Outbox 经真实 HTTP 发送；操作记录器只记录实际响应/异常，不生成或替换服务端结果。

1. 实际停止**专用** API。旧 Outbox 记录真实 ConnectError，按原退避机制重试，共记录 27 次传输失败；期间 pending=6、rejected=0，未删除或重写原业务结果。
2. 实际启动同一专用 API，等待其恢复。旧 Outbox 不换业务键或租约，继续按退避发送原载荷。
3. 6 个完成请求均实际成功，服务端均返回 duplicate=true、status=completed。最终 pending/rejected/orphaned 均为 0，6 份专用 ack 记录已写入，发送进程退出 0。

这是**已经被历史服务接受的完成结果**在严格新 API 上的真实重复投递与网络恢复，不是首次未确认完成、响应丢失或真正缺少版本载荷的全部验收。源载荷原本已由旧模型序列化包含版本，不人为删除版本字段构造“历史 outbox”。因此无需兼容头，旧完成摘要仍匹配，过期原 lease 也不会被误用来开启新执行。

## 旧 SDK 与冻结评分器的两个真实组合

两个 Runner 均配置 execution_slots=0、score_slots=1；不领取业务执行。所有评分输入、产物下载、大小/SHA-256 校验、独立子进程运行、lease 心跳和结果上报都走实际产品代码及严格 API。

| 组合 | 实际操作与结果 |
| --- | --- |
| 旧 6473c96 Supervisor/Worker/SDK + 原冻结评分器 | 管理 API 对原三个成功 Attempt 分别 rescore，均 201；旧 Runner 实际领取和下载原清单产物，3 个新 ScoreRun 均 completed/pass，原四项检查各 4/4，共 12/12 |
| 新 3aa7e50 Supervisor + 独立旧 6473c96 Worker/SDK + 原冻结评分器 | 停止上一 Runner 后再次创建 3 个 rescore；Binding.python 指向独立旧 venv，实际子进程加载旧包及冻结评分器，3 个新 ScoreRun 均 completed/pass，各 4/4，共 12/12；新 Supervisor 按严格 ScoreOutput 校验并经 API 接受 |

后一组合证明保留旧插件及对应旧运行环境可以服务新控制端/新 Supervisor。它不证明原插件直接加载进新严格 SDK 会兼容：旧源码构造 ScoreOutput 时依赖 Python 默认版本，仍应按升级说明保留旧环境，或者修改生产端后发布新的插件摘要/版本。

## 历史与额度核对

经副本公开 API 保存前后 CaseRun/Attempt、score_runs、manifests 和 operations。核对结果：

- 三个原 Attempt ID 集合完全相同，没有新业务 Attempt；原执行结果和 Manifest 列表内容完全相同。
- 所有原 ScoreRun 记录保持相同，仅追加本次 6 个评分记录；最早评分仍是原记录，没有调用创建回归报告的接口。
- 原 6 份源 journal 字节 SHA-256 前后相同。重传只得到已有完成确认，没有新工作或新的执行额度占用。
- 两组评分各按独立评分容量领取，完成后释放相应评分额度；没有未知业务被自动释放额度。

这些比较及 API/容器日志保存在本次私有目录，未发布任务输入、模型密钥、平台/Agent 令牌或私有产物。

## 命令、记录与剩余边界

核心操作为 `git archive 6473c96 src/eyes integrations`、在专用副本运行 pg_ctl 和 Alembic、专用 docker run/stop/start、原版 Outbox.flush/ControlClient、公开 `POST /v1/attempts/{id}/rescore`、原 eyes-runner main 的 score-only 配置，以及公开 GET case-runs/operations/artifact content。没有修改仓库产品或测试代码来制造成功。

私有记录包含 versions、runtime-inspection、baseline/final case-runs/operations、两组 rescore 请求、旧 outbox 来源摘要、27 次失败及 6 个实际响应、outbox 最终状态、全部组件日志、评分 journal 和 summary。Docker 启动的 Inference/Secrets 两次失败及临时目录备份均保留；首次停止后进程尚未退出的检查阻止了目录移动，确认退出后才继续。

本次完成的范围是：既有完成载荷的旧版真实网络重传，以及以上两个旧 SDK/冻结评分器组合。仍未覆盖：真正缺少版本的历史 outbox、首次提交响应丢失、旧 SDK 与所有外部 exporter/插件二进制、多进程竞争、更早 evidence_wait_seconds 缺省快照重放。未知远端任务的整体 Runner 崩溃/停止确认矩阵属于前一任务，仍未验收；本次没有启动 Agent，不宣称 M0/M2 全面通过。
