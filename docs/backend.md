# 控制后端开发说明

当前实现 Eyes 的控制后端基础及配套 Runner。Agent 端入口、HTTP 协议、SDK 与评分器说明见 [接入文档](agent-integration.md)。源码按 AGENT.md 的模块边界组织；HTTP 路由负责认证和协议转换，领域模块负责校验、状态及事务。当前不具备 M1 真实闭环验收结果，具体证据见 [验证记录](backend-validation.md)。

## 当前实现与后续工作

| 范围 | 当前情况 |
| --- | --- |
| 公共协议 | 目标、JSONL 用例、评分、事件与产物的 Pydantic 模型及 JSON Schema |
| 基础认证 | 项目管理、只读和 Runner 令牌；数据库保存 SHA-256 摘要；可撤销 |
| 版本与实验 | 发布不可变版本；冻结实验；幂等创建；同事务创建用例运行和工作项 |
| 调度 | 主动领取、插件匹配、执行/评分容量、租约、心跳、令牌校验、取消及到期扫描 |
| 证据 | 事件去重、冲突诊断、固定清单、迟到清单、受控产物上传及查询 |
| 评分 | 固定清单绑定、前置证据检查、结果校验、重新评分历史及明确分母的结果查询 |
| 部署 | Alembic 初始迁移、配置样例、Compose 的 PostgreSQL/API/调度进程/迁移服务 |
| 实际执行组件 | 宿主机 Runner、HTTP/Python 适配器、独立规则/Python 评分进程、SDK、插件摘要与本地状态 CLI 已实现；真实目标联调暂缓 |
| Web 控制台 | React/TypeScript/Vite 页面及公开 API 操作已有实现，结果比较为事实并列视图；验证边界见 [前端说明](frontend.md) |
| 回归与运维 | 固定回归报告、质量门槛、开发者 CLI、证据等待/封存、保留删除/文件回收、审计及备份恢复已有实现；用法见 [平台说明](platform.md) |

本轮 PostgreSQL 验证覆盖迁移、报告持久化、排队取消和数据库备份恢复，见 [平台验证记录](platform-validation.md)。多 Runner、活动任务取消、含执行证据的恢复及真实 Agent 链路仍待验收。

## 本机运行

需要 Python >=3.14、uv 和可连接的 PostgreSQL。依赖锁定在根目录 `uv.lock`；本次在 macOS ARM64、CPython 3.14.7 上安装成功。

```sh
uv sync --frozen
cp .env.example .env
```

编辑 `.env`，设置 `EYES_DATABASE_URL=postgresql+psycopg://用户名:密码@主机:端口/数据库`。特殊字符需按 URL 规则编码。服务只接受 PostgreSQL/psycopg 连接。

```sh
uv run alembic upgrade head
uv run eyes-admin bootstrap --name default
uv run eyes-server
```

`bootstrap` 创建一个项目并输出 `project_id`、`credential_id`、管理 `token`。输出发生在事务提交后，令牌只能在签发时取得。保存该令牌，使用 `Authorization: Bearer <token>` 调用业务 API。

另一个终端使用相同配置运行：

```sh
uv run eyes-scheduler
```

`uv run eyes-scheduler --once` 执行一次到期扫描。默认每 5 秒扫描；租约 60 秒、停止请求协调期限 60 秒；全局执行容量 16、评分容量 4。项目默认执行容量 8、评分容量 2。这些是开发默认值，尚无容量实测依据。API 和调度进程必须使用一致的配置及数据库。

API 默认监听 `127.0.0.1:8000`。更改监听参数可直接运行：

```sh
uv run uvicorn eyes.server.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

`/docs` 和 `/openapi.json` 提供接口说明。`/health/live` 检查进程；`/health/ready` 检查数据库连接和迁移版本，未就绪返回 503。就绪检查同时验证产物卷可写性。

## Compose

```sh
cp deploy/.env.example deploy/.env
openssl rand -hex 32
```

将生成的十六进制密码写入 `deploy/.env` 的 `POSTGRES_PASSWORD`，然后运行：

```sh
docker compose --env-file deploy/.env -f deploy/compose.yaml up --build -d
docker compose --env-file deploy/.env -f deploy/compose.yaml exec api eyes-admin bootstrap --name default
```

Compose 等待 PostgreSQL 健康后执行迁移，再启动 API 和调度进程。相关依赖条件见 [Docker Compose 文档](https://docs.docker.com/compose/how-tos/startup-order)。PostgreSQL 18 的持久卷挂载在 `/var/lib/postgresql`，与 [官方镜像的目录约定](https://hub.docker.com/_/postgres)一致。

数据库和 API 端口都只映射到本机。数据库与证据分别使用独立数据卷。当前 Compose 包含控制端和 Web 控制台，本机前端端口为 8080；Runner 在目标宿主机独立运行。本轮部署的实际验证范围见 [平台验证记录](platform-validation.md)。

## 令牌及项目范围

| 角色 | 权限 |
| --- | --- |
| read | 查询版本、实验、结果、证据及运行状态 |
| manage | 读取、发布版本、导入数据集、创建/取消实验、核对未知状态、重新评分 |
| runner | 注册、领取授权工作、续租、上报；按获授权的 Attempt 上传证据 |

签发只读令牌：

```sh
uv run eyes-admin issue-token --project-id <项目UUID> --role read
```

签发仅允许某个目标版本的 Runner 令牌：

```sh
uv run eyes-admin issue-token --project-id <项目UUID> --role runner \
  --target-id <TargetVersion UUID> --work-kind execute --work-kind score
```

`--target-id` 可重复传入；允许项目所有目标版本时显式使用 `--all-targets`。Runner 令牌必须指定工作类型。首版一份 Runner 凭据对应一个注册身份，多 Runner 使用不同凭据。令牌撤销命令为：

```sh
uv run eyes-admin revoke-token --credential-id <凭据UUID>
```

项目身份从令牌取得，API 请求不接受客户端指定的 `project_id`。Runner 通过 API 工作，不连接数据库。评分 Runner 可读取其获授权评分清单中的产物；执行 Runner 可访问自己执行的 Attempt 的产物。

## 公共契约

模型位于 `src/eyes/contracts/`，不依赖后端 ORM。协议当前为 `1.0`，缺省 `schema_version` 按 `1.0` 解析，其他版本返回校验错误；未知字段被拒绝。`GET /v1/contracts` 返回四类协议的 JSON Schema。

目标版本的 `name` 是项目内稳定的目标名称。发布相同名称会建立新 TargetVersion，并关联同一 Target 容量池。它们共享固定的 `concurrency_limit`；此轮没有容量编辑接口，改变同名目标的容量会返回 409。接入方须用同一名称表示同一目标。并发大于 1 要同时声明会话和环境隔离。

目标协议包含 `capabilities/prepare/execute/cleanup`；可选取消与状态核对由能力声明控制。`adapter` 和评分器 `plugin` 是 Runner 上已安装插件的标识。领取时匹配已注册的 Python 别名/能力和 HTTP 地址 origin，本机 TOML 配置可信入口与地址白名单；评分运行前由 Runner 核对实现摘要。敏感头值使用 `secret_refs`，发布配置拒绝已知敏感字段，包含 `X-API-Key` 等常用头名。

测试集通过 `DatasetImport.jsonl` 整体导入。每行格式例如：

```json
{"schema_version":"1.0","case_id":"answer-001","input":{"message":"说明该项目的用途"},"expectations":{"required_terms":["Agent"]},"tags":["smoke"],"environment":{},"artifact_requirements":[],"steps":[]}
```

`input` 是结构化对象。支持预期、标签、产物要求、准备逻辑版本和外部环境限制；具体产物内容或业务状态由已安装评分器判断。空行、无效 JSON、重复 `case_id`、错误字段和非空 `steps` 都报告行号，整个版本不发布。当前仅支持单轮。

ScorerVersion 冻结插件标识、实现摘要、配置、证据要求、超时及可选数值语义。评分状态和质量结论分别记录；数值范围、方向、阈值及结论一致性由后端校验。规则与可信 Python 评分器在 Runner 的独立进程中执行。

执行事件包含生产者、序号、发生时间、Attempt、trace/span、来源及数据。生产者序号仅用于该生产者的顺序；API 列表按接收时间和记录 ID 返回，不表示全局执行顺序。外部 trace 须通过 `linked_trace_ids` 显式链接该 Attempt 的执行 trace。

## API 清单

除健康检查、OpenAPI 和交互文档外，下面接口均需对应角色的 Bearer 令牌。

| 操作 | API | 角色 |
| --- | --- | --- |
| 发布目标/评分器 | `POST /v1/targets`、`POST /v1/scorers` | manage |
| 整体导入 JSONL | `POST /v1/datasets/import` | manage |
| 版本列表与详情 | `GET /v1/catalog/{targets,datasets,scorers}[/{id}]` | read/manage |
| 契约 Schema | `GET /v1/contracts` | read/manage |
| 创建实验 | `POST /v1/experiments`，必需 `Idempotency-Key` | manage |
| 实验列表/详情 | `GET /v1/experiments[/{id}]` | read/manage |
| 汇总及用例详情 | `GET /v1/experiments/{id}/results`、`/case-runs` | read/manage |
| 取消实验 | `POST /v1/experiments/{id}/cancel` | manage |
| 注册与领取 | `POST /v1/runners/register`、`POST /v1/work/claim` | runner |
| 固定评分输入 | `POST /v1/work/{id}/score-input`（身份与有效 lease token） | runner |
| 心跳与进度 | `POST /v1/work/{id}/heartbeat`、`/progress` | runner |
| 执行/评分结果 | `POST /v1/work/{id}/execution-result`、`/score-result` | runner |
| 未知执行核对 | `POST /v1/attempts/{id}/resolve` | manage |
| 新建评分记录 | `POST /v1/attempts/{id}/rescore` | manage |
| Attempt 与核对来源 | `GET /v1/attempts/{id}` | read/manage |
| 事件批量接收 | `POST /v1/events` | runner |
| 事件及清单 | `GET /v1/attempts/{id}/events`、`/manifests` | read/manage |
| 初始化产物 | `POST /v1/attempts/{id}/artifacts` | runner |
| 上传/下载产物内容 | `PUT/GET /v1/artifacts/{id}/content` | 授权 runner；下载亦允许 read/manage |
| 工作状态及 Runner 心跳 | `GET /v1/operations` | read/manage |

列表接口采用 `limit/offset`，默认 50 条（事件 100 条），上限 200。未找到项目内记录返回 404，权限不足 403，冲突 409，契约错误 422，载荷超限 413，数据库不可用 503。事件接收和状态变更在事务提交后才确认。

## Runner 必须遵守的执行顺序

1. 注册 `supported_schema_versions`、可执行的 `adapters/scorers`、Python 别名及能力 `python_agents` 和规范化 `http_origins`。收到协商版本和 `runner_id` 后领取兼容的 `execute` 或 `score` 工作；无可领取工作返回 `work: null`。
2. 保存工作 ID、领取令牌和有效期。在有效期内持续心跳；所有状态上报带 `runner_id/lease_token`。
3. 执行工作先上报 `preparing`，完成准备后上报 `running`。只有服务端确认 `running` 写入后才能调用目标，这条确认是执行意图边界。
4. 使用分配的独立上下文、截止时间、幂等键和 trace context；上传事件与产物，并执行清理。
5. 上报 `ExecutionResult`，明确输出/错误、清理状态、证据状态和 `dropped_events`。清理当前随最终执行上报一次；后续独立清理记录接口待实现。
6. 评分领取获得小型 `ScoreAssignment`，通过有效租约读取完整固定 `ScoreInput`，使用私有只读文件传入独立进程；输入默认上限 32 MiB，独立于进程控制消息上限。评分返回时记录 `completed_at`，落实本地超时及清理后上报 `ScoreOutput`。Runner 已实现进程组控制、墙钟超时及可配置 POSIX 资源限制，具体范围见接入文档。

同一次操作的传输重试复用幂等键；新业务执行使用新 Attempt。目标声明不支持幂等时不得自动重复未知调用。Runner 也必须实际落实其声明的隔离及插件行为，注册能力不是执行证明。

## 状态与恢复

| 触发 | 控制端行为 |
| --- | --- |
| 正常执行 | `claimed → preparing → running → succeeded/failed` |
| 取消排队工作 | 取消该工作及用例运行，不制造实际执行 Attempt |
| 取消活动执行或截止到达 | 请求停止；心跳返回 `cancel_requested` |
| 上报 cancelled/timed_out | 必须声明已确认目标停止 |
| 执行意图之前失联 | 保留失败 Attempt；允许新工作重新排队，默认最多 3 个准备尝试 |
| 执行意图之后租约失效 | `unknown`，旧令牌失效，额度继续占用 |
| 停止请求超过协调期限 | `unknown`，继续保留额度 |
| 已知未知状态的人工核对 | 管理角色提供停止确认及原因；追加来源记录，才释放额度 |
| 评分超时或失联 | 计算截止后停止评分，默认另有 60 秒提交按时结果/错误诊断；租约失效或提交窗口结束时记 error；显式 rescore 创建新记录 |
| 重复最终结果 | 同领取令牌、同内容返回原接收结果；不同内容返回冲突 |
| 旧 Runner 迟到状态 | 失效令牌不能修改调度；已授权 Attempt 的迟到事件仍可保存 |

领取、额度判断、令牌及恢复使用同一组按固定顺序获取的 PostgreSQL 事务 advisory lock。额度从 `reserved` 工作项计算；未知执行仍计入全局、项目和稳定目标的执行容量。符合条件的队列使用 `FOR UPDATE OF work_items SKIP LOCKED` 领取。初版将这些事务串行协调，吞吐需实测；不承诺公平性或外部副作用恰好一次执行。

完整评分输入读取只校验项目、身份、工作范围、有效租约与计算期限，不持有全局调度锁；只读取已分配的固定清单。`EYES_MAX_SCORE_INPUT_BYTES` 控制响应大小，Runner 使用相同的 `max_score_input_bytes`。API 与 scheduler 的 `EYES_SCORE_SUBMISSION_GRACE_SECONDS` 必须一致；提交宽限不延长计算期限，也不恢复已失效租约。完成结果与证据在 Runner 中分别发送，证据的重试不会阻塞结果发送锁。上述评分输入协议变更要求三类进程同步升级；最新平台功能另需 `0002_platform`，详见 [平台升级说明](platform.md) 及 [接入兼容性](agent-integration.md#6-兼容性与验收边界)。

数据库触发器保护版本、事件、清单、核对记录、实验配置、已发布评分和回归报告；事件与清单仅允许按严格过期规则清除载荷，保留原摘要与标识。Attempt 的核对会保留先前结果及来源，已固定清单保存自己的执行结果副本。

实验 `completed` 表示调度工作已结束；可能仍有执行失败、评分错误或证据不足。存在未知工作时为 `completed_with_unresolved`。结果查询同时展示计划运行数、成功数、评分数、通过数及未解决数，比例返回明确的 numerator/denominator。初版汇总选首个成功 Attempt 和其最早的 ScoreRun；重新评分的完整历史在用例详情中读取，汇总不会自动换成新分数。comparison 模块可选择固定 ScoreRun 并生成不可变回归报告。

## 证据、产物与敏感内容

事件按项目、生产者和 event_id 去重，对原始规范化内容计算摘要。相同 ID、不同内容返回 409 并记录不含载荷的诊断。输入输出、事件、产物均通过清单引用关联；清单冻结执行结果。后到事件或产物产生新清单，原评分继续引用原清单。未报告的丢弃数量为未知，不能默认当作零。

完成执行时按当前清单检查评分前置证据。新实验按 `evidence_wait_seconds` 等候缺失证据，到期仍不足则记录 `insufficient_evidence`。Runner 将待确认或被拒绝的证据标为 partial，迟到上传完成后通过 evidence-close 追加封存清单。超过服务端等待期的证据需显式重新评分。评分的引用必须属于其清单，引用的产物还需可读取。`sealed` 仅表示声明的采集范围封存。

产物以 Attempt 和完整元数据的摘要确定稳定 UUID，同内容登记重传复用已有记录；先以名称、大小和 SHA-256 登记为 pending，再向服务端指定的 UUID 上传二进制内容。服务端验证大小和摘要，写临时文件、fsync、发布后才登记 ready。原始文件名不参与存储路径，下载采用附件形式。文件已发布但事务未提交时可重传同一 pending 上传；`eyes-ops maintain` 提供未登记文件、遗留临时文件和长期 pending 的预览与回收，执行前保护活动工作和证据等待。

目标与评分器配置拒绝已知密钥字段及 URL 内嵌凭据，改用 `secret_refs` 保存运行环境引用。执行结果和事件递归掩码已知敏感字段。自由文本、用例输入和二进制产物需要生产者在上传前脱敏；当前没有通用秘密识别器。JSON 请求默认上限 8 MiB，产物默认 32 MiB。保留与删除策略由 `eyes-ops` 执行，默认不按年龄删除完整证据；范围见 [平台说明](platform.md)。

API 使用 OTel SDK 创建实际 HTTP 请求 span，接收 W3C Trace Context，并返回 `X-Eyes-Trace-Id`。设置 `EYES_TRACE_CONSOLE_EXPORT=true` 可将这些 span 输出到控制台。Attempt 和 ScoreRun 各有独立 trace context，Runner 创建实际执行根 span，评分根通过 OTel Link 关联执行。执行 span 进入证据接口，评分 trace 当前保留在本机。当前没有 OTLP exporter、查询后端或完整 Agent 内部链路证明。

## 迁移、备份与后续验收

迁移入口是 `alembic.ini` 和 `migrations/versions/`，当前 head 为 `0004_experiment_batches`。迁移只在显式命令/Compose migrate 服务中运行，API 启动不自动建表。升级前备份数据库和证据卷，并记录应用版本与迁移版本。恢复时需要检查每个 ready 产物的路径、大小和摘要，以及评分引用的清单。`eyes-ops backup/restore/audit` 提供可执行流程，命令和验证边界见 [平台说明](platform.md)。

已提供 `eyes-server`、`eyes-scheduler`、`eyes-admin`、`eyes-runner`、开发者 CLI `eyes` 和运维 CLI `eyes-ops`。新增回归、封存和评分重试端点见 [平台说明](platform.md)。

HTTP 与 Python 通用接入功能已有实现，按本次要求暂缓真实 Agent 联调。后续恢复验收时，在可运行的 PostgreSQL 环境执行迁移，接入两个真实 Agent，运行导入、领取、执行、证据查询和独立评分。之后再验证多 Runner 限额、租约过期、取消、迟到上报和评分故障。原始结果须按 [AGENT.md](../AGENT.md) 的阶段要求保存。

多 Agent 批次新增公开 API 和 CLI，在同一事务创建多份独立实验，详见 [多 Agent 批次](multi-agent-batches.md)。
