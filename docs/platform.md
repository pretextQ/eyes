# 回归、证据与运维

校准日期：2026-10-09。本文主体描述 `0002_platform` 引入的平台功能，当前迁移 head 已是 `0004_experiment_batches`。公开 API、开发者 CLI、本地运维 CLI 和 Web 固定回归报告均已有实现；Web 支持显式选择历史评分，行为验收尚未完成。Python 真实接入已有记录，HTTP 仍待验收。历史运维验证边界见 [平台验证记录](platform-validation.md)，当前进度见 [开发计划](PLAN.md)。

## 升级与兼容

```sh
uv sync --frozen
uv run alembic upgrade head
uv run eyes-server
# 另一个终端
uv run eyes-scheduler
```

升级前停止控制端、调度器及维护进程，备份数据库和证据卷；升级后一起重启 API、Scheduler、Runner。完整迁移链为 `0001_control_plane → 0002_platform → 0003_observation → 0004_experiment_batches`；0002 新增回归报告、证据等待记录、证据过期时间和评分取消时间，后两版分别增加被动观测与实验批次。当前 API 就绪检查要求 0004，并通过实际产物发布与读取路径检查证据卷，不能仅升级到 0002 后运行当前服务。

协议仍为 `1.0`。新增 `ExperimentCreate.evidence_wait_seconds`，新实验默认 60 秒，可设 0；历史实验快照缺少该字段时沿用即时评分。旧实验创建请求重试时，未显式传入新字段仍按原摘要判断幂等。旧 Runner 可继续上报，升级 Runner 后支持迟到上传完成后的 `evidence-close`。新版 Runner 对旧 API 的封存请求会失败，因此先升级服务端。

## 1. 固定回归报告与 CI

### 创建报告

`POST /v1/comparisons` 需要管理令牌和 `Idempotency-Key`。请求包含两次实验、明确的评分器配对、门槛和可选 ScoreRun 选择。用具体 UUID 替换下列占位内容，保存为 `comparison.json`：

```json
{
  "baseline_id": "BASELINE_EXPERIMENT_UUID",
  "candidate_id": "CANDIDATE_EXPERIMENT_UUID",
  "scorer_pairs": [
    {"baseline_id": "BASELINE_SCORER_UUID", "candidate_id": "CANDIDATE_SCORER_UUID"}
  ],
  "baseline_score_ids": [],
  "candidate_score_ids": [],
  "gate": {
    "max_regressions": 0,
    "min_comparable_coverage": 1,
    "min_candidate_pass_rate": 1,
    "min_execution_success_rate": 1,
    "numeric_tolerance": 0
  }
}
```

- 默认固定每个 CaseRun 的首个成功 Attempt 和该评分器最早的 ScoreRun。可显式指定重新评分记录；每个 Attempt/评分器只能指定一个，并校验项目、实验、Attempt 与评分器归属。
- 报告保存选择的记录 ID、清单摘要、评分结果、证据引用、汇总、比较配置及门槛结果。数据库拒绝更新已发布报告。后续重评分、迟到证据或实验状态变化不改变旧报告；使用新请求键创建新报告。
- 同请求键和参数返回原报告，同键不同参数返回 409。
- 以 `case_id + repetition` 对齐，检查用例内容摘要、评分器完整摘要、执行配置和目标能力。不同内容、缺失用例、N/A、评分错误、证据过期及执行不成功有明确原因，不计为质量改善或通过。
- 目标版本是比较变量。目标配置改变、外部版本未知、外部环境不能快照会给出提示。数据集整体变化后仍按单个用例摘要判断。
- 同一用例先对重复运行求均值，再对用例等权汇总。数值方向遵循评分器声明；`numeric_tolerance` 使用评分器原始单位。通过率下降或方向修正后的数值下降超过容差记为退化；不宣称统计显著性。
- 默认要求全部用例可比、候选执行成功、有效评分全部通过且无退化。配置可以降低覆盖率要求，但未知执行和没有有效评分仍产生无法判定项。已确认的门槛失败优先返回 `fail`，否则有缺口返回 `inconclusive`，全部满足才是 `pass`。
- 两次实验尚未结束时也能生成报告，用于记录当前缺口；它不会自动变为最终报告。

读取接口：`GET /v1/comparisons`、`GET /v1/comparisons/{id}`、`GET /v1/comparisons/{id}/gate`。列表支持 `limit/offset`，只读角色可读取项目内报告。

### CLI

令牌通过环境变量传递。`EYES_URL` 默认 `http://127.0.0.1:8000`；也可使用 `--url`、`--token-env` 和 `--timeout`。

```sh
# EYES_TOKEN 由运行环境注入，避免写入命令历史。
uv run eyes import-dataset --name regression --file cases.jsonl
uv run eyes create --file experiment.json --key release-42-experiment
uv run eyes list
uv run eyes get EXPERIMENT_UUID
uv run eyes wait EXPERIMENT_UUID --deadline 600
uv run eyes results EXPERIMENT_UUID
uv run eyes compare --file comparison.json --key release-42-comparison
uv run eyes report REPORT_UUID
uv run eyes gate REPORT_UUID
uv run eyes cancel EXPERIMENT_UUID
uv run eyes retry-score SCORE_RUN_UUID
uv run eyes rescore ATTEMPT_UUID
```

`create` 的 JSON 使用 `ExperimentCreate`，与 Web 创建接口相同。所有命令输出 JSON；不直接访问数据库、不自动重试写请求、不把令牌放在参数中。

`create` / `compare` 校验请求文件后只发送显式提供的字段，由 API 补齐默认值。旧实验请求未提供 `evidence_wait_seconds` 时，CLI 保留这一信息，让服务端按旧请求摘要识别幂等重试；显式提供的值仍参与参数冲突校验。

CI 应以 `eyes gate` 的退出码决定结果：

| 退出码 | 含义 |
| --- | --- |
| 0 | 门槛通过 |
| 1 | 确认未达门槛 |
| 2 | 无法判定；`wait` 超时或含未知执行也使用此码 |
| 3 | 配置、认证、服务或响应错误 |

`wait` 只等待调度结束，成功退出不代表评分通过。CI 最后必须调用 `gate`。命令参数解析错误也使用 3，与无法判定的 2 区分。

## 2. 服务端证据等待和取消

执行成功后，服务端逐个检查评分器需要的输入、输出、事件、产物和 sealed 声明：

1. 已满足的评分器立即生成绑定固定清单的 ScoreRun。
2. 缺少证据且等待期大于 0 时，创建独立的 `EvidenceWait`；等待不占用执行或评分配额，实验仍保持活动状态。
3. Scheduler 周期检查最新清单。证据到齐后创建 ScoreRun；到期时只考虑截止前已持久化的清单，仍缺证据则生成 `insufficient_evidence`。
4. 原 ScoreRun 不重绑新清单。超过等待期的证据形成新清单，需要显式 `rescore` 才会纳入。

`GET /v1/attempts/{id}` 返回等待记录；`/v1/operations` 返回等待数量、最老排队时间和评分错误数。

执行 Runner 可以 `POST /v1/attempts/{id}/evidence-close`，提交 `status`、`dropped_events`、`details`。需已完成或已核对执行，并且该 Runner 有对应 Attempt 权限。pending 产物不允许 sealed；完全相同的封存声明复用已有清单。sealed 始终只代表声明的采集范围。

新版 Runner 在完成上报得到确认后保留本地目录；剩余证据上传完成后，通过持久化 outbox 发出封存声明。只有生产者原先声明 sealed、没有采集失败/截断/丢失等缺口且上传全部确认，才把仅因传输积压造成的 partial 恢复为 sealed。收到封存确认后才回收正常工作目录。被拒绝或无法转移的数据继续保留，供运维检查。

封存前重新核对本地待转移文件、outbox 待上传和被拒绝记录。全部清空后，封存声明中的 `local_transfer_failures` 归零，原完成上报时的计数保留在 `local_transfer_failures_at_completion`。采集失败、截断、丢弃和执行事实持久化失败仍会阻止恢复 sealed；原完成请求、已发布清单和评分不改写。

取消实验现在同时处理执行任务、等待证据、排队评分和活动评分。等待/排队评分记录 skipped；活动评分收到心跳停止请求，其后提交的结果不再计为有效分数。未按时结束或失去租约保留 error 诊断。对外部执行仍保留原规则：取消未确认保持未知状态和配额，不因租约过期自动重新执行。

评分失败可以调用 `POST /v1/score-runs/{id}/retry`：新建 ScoreRun，保留原评分器和原清单，不执行目标。`rescore` 则使用最新清单；初始证据等待尚未结束时拒绝提前重新评分。汇总仍选择最早评分，使用新评分做回归时要在报告请求中明确指定对应 ScoreRun。

## 3. 证据生命周期与部署运维

### 审计和清理

```sh
uv run eyes-ops audit
uv run eyes-ops maintain
# 审阅上一步清理计划后执行
uv run eyes-ops maintain --apply
# 显式删除一个已结束、无待执行评分/证据等待的 Attempt 的证据载荷
uv run eyes-ops maintain --attempt-id ATTEMPT_UUID
uv run eyes-ops maintain --attempt-id ATTEMPT_UUID --apply
```

- `EYES_EVIDENCE_RETENTION_DAYS=0` 默认禁用按年龄过期；正整数按 Attempt 结束时间计算。
- `EYES_PENDING_ARTIFACT_TTL_HOURS=24`：回收已结束且无活动工作/证据等待的长期 pending 产物。
- `EYES_ORPHAN_ARTIFACT_GRACE_HOURS=24`：回收超过宽限期的未登记 UUID 文件、`.pending-*` 和遗留健康检查临时文件。忽略其他文件和符号链接。
- 活动、未知、等待评分、等待证据的 Attempt 不会被过期。数据库先提交过期标记，再重新获取维护锁核对并删除文件；中途退出留下可再次回收的过期文件。
- 过期会清除事件 data、清单内的输入/预期/结果副本、Attempt 结果载荷和产物文件，保留标识、原摘要、引用、过期时间及历史评分/报告。原摘要用于标识原内容，不是过期占位内容的摘要。
- 数据集版本、评分理由、人工核对记录和备份有独立保留周期，此命令不是全项目擦除。评分器应避免把敏感输出全文复制到理由中。
- 已过期证据不能重新上报、下载或评分。API 返回 410，历史查询通过 `expired_at` / `evidence_expired_at` 与 expired 状态表达不可读。

`audit` 检查 ready 文件大小/SHA-256、清单与事件/产物的归属、评分引用。异常返回退出码 1；命令/环境错误返回 3。

可由宿主机调度器定期执行 `maintain --apply`；也可在 Compose 显式启用维护进程：

```sh
docker compose -f deploy/compose.yaml --profile maintenance up -d
```

维护进程每小时执行一次；默认保留期 0 不会按年龄清除完整证据，但会清理符合条件的过期 pending 和孤立文件。

### 一致性备份

所有新版 API 数据库事务、Scheduler 和管理命令配合维护锁。备份获取独占锁，检查数据库版本及存储引用，用 `pg_export_snapshot` 和 `pg_dump` 导出同一数据库快照，并复制所有 ready 产物；最后写完成清单和摘要。未完成上传只保留数据库元数据。

本机有匹配数据库主版本的 PostgreSQL 客户端时：

```sh
uv run eyes-ops backup /secure/backups/eyes-20261003 --pg-bin-dir /path/to/postgresql/bin
```

数据库在 Docker 时，可从宿主机使用服务它的 PostgreSQL 容器内工具：

```sh
uv run eyes-ops backup /secure/backups/eyes-20261003 --pg-container POSTGRES_CONTAINER_NAME
```

此容器必须对应 `EYES_DATABASE_URL` 的数据库实例，内部端口为 5432。备份的文件卷必须与 API 使用同一个卷。目录必须不存在，并位于证据卷之外。命令把 PostgreSQL 密码放入子进程环境，不输出密码。

维护锁会暂时阻止业务数据库请求。首版建议在维护窗口暂停新实验、等待活动执行结束，并停止 Runner 后备份，避免长备份导致心跳超时。旧版本服务、直接 SQL 写入和数据库迁移不受应用维护锁约束，因此升级前应先停止写入端，使用 PostgreSQL 原生 dump 与证据卷副本留存原版本备份。备份包含业务数据和凭据摘要，应保存在权限受控的目录，另行配置异机保留与加密。

### 恢复

恢复只支持空数据库和空证据目录，拒绝覆盖现有业务数据。先创建空数据库，然后设置恢复目标的 `EYES_DATABASE_URL` 和 `EYES_ARTIFACT_ROOT`：

```sh
uv run eyes-ops restore /secure/backups/eyes-20261003 --pg-container POSTGRES_CONTAINER_NAME
uv run eyes-ops audit
uv run alembic current
```

恢复会先校验 dump/文件摘要、使用单事务恢复数据库、发布证据目录，再做引用审计。恢复失败时保持服务停止，检查错误并使用新的空目标重试；数据库恢复与文件系统发布不是一个跨系统原子事务。

恢复后撤销所有旧 Runner 令牌，并使活动租约失效。未发执行意图的任务按既有规则恢复；已可能发生外部副作用的任务保留 unknown 及配额，需要核对真实状态后再签发新 Runner 令牌。管理和读取令牌保留。

### 部署与容量边界

Compose 包含 PostgreSQL、一次性迁移、API、Scheduler、Web 及可选维护进程。API/数据库仅映射本机；可通过 `EYES_API_PORT`、`EYES_POSTGRES_PORT`、`EYES_WEB_PORT` 改变宿主机端口，默认 8000/5432/8080。`EYES_CONTROL_IMAGE` 设置控制端共用镜像名。证据使用单机卷，未引入外部消息中间件。恢复、迁移和清理均有实际命令，不能据此宣称高可用。

当前配置上限仍为 JSON 请求 8 MiB、单产物 32 MiB、评分输入 32 MiB、单实验最多 100000 个 CaseRun。回归报告读取所选两次实验的评分记录，审计/备份遍历完整记录和文件；大型数据集需要预留维护时间和内存。尚无真实 Agent 吞吐、并发故障恢复和容量实测，不提供未经测量的性能承诺。

### Compose 命名卷的停写备份与恢复

Docker Desktop 的命名卷不直接暴露为宿主机目录。前面的 `eyes-ops backup --pg-container` 适用于宿主机能读取同一证据目录的部署；默认 Compose 命名卷使用下面的停写流程。不要把空的宿主机目录冒充证据卷。

先停止目标宿主机 Runner，再在项目根目录执行；保持原 Compose 项目名和环境配置：

```sh
set -e
EYES_BACKUP_DIR=/secure/backups/eyes-compose-20261003
mkdir -m 700 "$EYES_BACKUP_DIR"
docker compose -f deploy/compose.yaml stop frontend api scheduler maintenance
docker compose -f deploy/compose.yaml run --rm --no-deps api eyes-ops audit
docker compose -f deploy/compose.yaml exec -T postgres \
  pg_dump -U eyes -d eyes --format=custom --no-owner --no-privileges \
  > "$EYES_BACKUP_DIR/database.dump"
docker compose -f deploy/compose.yaml cp api:/app/data/artifacts "$EYES_BACKUP_DIR/artifacts"
docker compose -f deploy/compose.yaml exec -T postgres \
  psql -U eyes -d eyes -Atc 'SELECT version_num FROM alembic_version' \
  > "$EYES_BACKUP_DIR/database-revision.txt"
(cd "$EYES_BACKUP_DIR" && shasum -a 256 database.dump > database.sha256)
# 确认上述命令均成功后恢复控制端；再由接入方恢复 Runner。
docker compose -f deploy/compose.yaml up -d
```

证据文件的摘要保存在数据库元数据内，恢复后的 `audit` 会逐项复核。备份期间所有写入端必须保持停止；不要同时运行另一个连接同库的 API、Scheduler 或维护命令。

恢复使用**新的 Compose 项目和空卷**。设置 `EYES_RESTORE_PROJECT`、密码和不冲突的宿主机端口；镜像需与备份数据库版本匹配。以下命令不会删除旧项目的卷：

```sh
set -e
EYES_BACKUP_DIR=/secure/backups/eyes-compose-20261003
EYES_RESTORE_PROJECT=eyes-restored
(cd "$EYES_BACKUP_DIR" && shasum -a 256 -c database.sha256)
docker compose -p "$EYES_RESTORE_PROJECT" -f deploy/compose.yaml up -d --wait postgres
# postgres healthy 后恢复，尚不启动 API、Scheduler 或 Runner。
docker compose -p "$EYES_RESTORE_PROJECT" -f deploy/compose.yaml exec -T postgres \
  pg_restore -U eyes -d eyes --single-transaction --exit-on-error --no-owner --no-privileges \
  < "$EYES_BACKUP_DIR/database.dump"
docker compose -p "$EYES_RESTORE_PROJECT" -f deploy/compose.yaml create api
docker compose -p "$EYES_RESTORE_PROJECT" -f deploy/compose.yaml cp \
  "$EYES_BACKUP_DIR/artifacts/." api:/app/data/artifacts
docker compose -p "$EYES_RESTORE_PROJECT" -f deploy/compose.yaml run --rm --no-deps --user root api \
  chown -R 10001:10001 /app/data/artifacts
docker compose -p "$EYES_RESTORE_PROJECT" -f deploy/compose.yaml run --rm --no-deps api eyes-ops audit
# 撤销旧 Runner 身份，使恢复前的进程不能提交；过期租约由 Scheduler 核对。
docker compose -p "$EYES_RESTORE_PROJECT" -f deploy/compose.yaml exec -T postgres \
  psql -v ON_ERROR_STOP=1 -U eyes -d eyes -c \
  "BEGIN; UPDATE credentials SET revoked=true WHERE role='runner'; UPDATE work_items SET lease_expires_at=CURRENT_TIMESTAMP WHERE status='claimed'; COMMIT;"
docker compose -p "$EYES_RESTORE_PROJECT" -f deploy/compose.yaml run --rm --no-deps scheduler eyes-scheduler --once
docker compose -p "$EYES_RESTORE_PROJECT" -f deploy/compose.yaml up -d
```

恢复后核对 unknown 工作，再签发新 Runner 令牌。降级迁移不会恢复已清除的证据载荷；要恢复旧版本完整数据，使用升级前的备份。
