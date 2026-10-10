# Eyes 统一 Agent 接入协议 v1

状态（2026-10-10）：**协议与数据契约已落地，Runner 客户端及持久化参考 HTTP 接入服务已实现；真实 HTTP 验收阻塞。** 外部接口由接入端提供，Eyes 控制 API 不提供这些执行路由。新接入使用 `agent_http`，旧 HTTP/Python 保留原行为；实现、兼容与责任见[运行时文档](agent-http-runtime.md)，实际检查和阻塞见[验证记录](agent-http-validation.md)。

## 1. 目标与边界

任何语言、框架实现的 Agent，只要实现相同的执行协议，就能通过同一种 Eyes 接入路径参加评测。Eyes 核心不导入外部 Agent 模块，也不根据 Pi、Deta、Zeta 等名称分支调用。

职责分为三部分：

- Eyes 控制端：保存实验、任务、配额、证据、评分与历史。
- Eyes Runner：领取工作，作为协议客户端提交任务、查询状态、接收证据并向控制端报告。
- Agent 接入端：实现本协议，将任务交给实际 Agent，并对自身的幂等、持久化、隔离、状态和停止确认负责。

接入端可以内置在 Agent 中，也可以是接入方部署的独立服务。私有调用方式仍需要在这个边界内转换，但实现一次即可复用；它不要求提交到 Eyes 仓库，也不要求使用 Python。已有 Deta/Zeta 桥接仅作为接入行为和验证案例参考。

协议统一任务封装、生命周期、资源和证据交换。业务输入仍由能力声明中的 `input_schema` 描述，Eyes 使用数据集提供该输入；不会要求所有 Agent 的业务参数相同。评分预期、评分器配置及 Eyes 管理/Runner 令牌不发送给目标。

## 2. 契约来源与版本

- 数据类型来源：[agent_protocol.py](../src/eyes/contracts/agent_protocol.py)。只依赖公共数据类型和 Pydantic，不依赖 ORM、Runner 或任一 Agent。
- 语言无关的类型定义：[agent-protocol-v1.schema.json](agent-protocol-v1.schema.json)，使用 JSON Schema 2020-12。每种消息通过 `#/$defs/AgentTask` 等引用单独校验；顶层是类型目录，不是一个通用消息的校验入口。
- HTTP 行为、状态转换、跨请求约束以本文为准。JSON Schema 覆盖字段、类型、边界和必填项；跨字段及跨请求语义还需接入方按本文实现。Python 类型提供部分跨字段校验，不以“Schema 校验成功”替代协议一致性验收。

重新生成类型定义：

```sh
uv run python -m eyes.contracts.agent_protocol > docs/agent-protocol-v1.schema.json
```

每个 JSON 消息显式携带 `protocol_version: "1.0"`，缺失版本不自动按当前版本解释。不认识的字段或版本明确拒绝；不静默忽略并继续运行。未来兼容性变化需发布明确的新契约，不能只修改某个接入端的私有行为。

## 3. HTTP 绑定

基地址由接入方配置，以下路径相对于基地址。JSON 使用 UTF-8，普通响应为 `application/json`；所有成功响应中的身份必须与请求一致。标准响应不返回实现栈、凭据或完整请求头。

| 必需 | 方法与路径 | 请求 / 响应 | 含义 |
| --- | --- | --- | --- |
| 是 | `GET /agent/v1/capabilities` | `AgentCapabilities` | 发现版本、输入格式、隔离、容量与可选能力 |
| 是 | `POST /agent/v1/runs` | `AgentTask` → `AgentRun` | 接受一次业务执行，首次成功为 202，同键重放为 200 |
| 是 | `GET /agent/v1/runs/by-key/{idempotency_key}` | `AgentRun` | 提交响应丢失后查询原执行，不新建工作 |
| 是 | `GET /agent/v1/runs/{run_id}` | `AgentRun` | 读取当前状态快照 |
| 是 | `GET /agent/v1/runs/{run_id}/result` | 200 `AgentResult`，或 202 `AgentRun` | 获取终态/未知结果；仍在执行时返回当前快照 |
| 否 | `POST /agent/v1/runs/{run_id}/cancel` | 无 body → `AgentCancelResult` | 请求取消；可安全重复调用 |
| 否 | `GET /agent/v1/runs/{run_id}/events?cursor=…&limit=…` | `AgentEventPage` | 读取统一事件封装，limit 为 1–200 |
| 否 | `PUT /agent/v1/resources/{resource_id}` | 文件字节 → `AgentResource` | 在提交前上传任务资源 |
| 否 | `GET /agent/v1/runs/{run_id}/artifacts/{artifact_id}` | 文件字节 | 下载该运行结果列出的产物 |

v1 先固定 HTTP+JSON，不同时引入 stdio、WebSocket 和多种推送路径。事件读取使用可重放分页，后续再根据实际需求增加流式传输。

认证使用接入端独立的 Bearer 凭据或部署约定的 mTLS。远程部署使用 HTTPS；可信本机调试可以使用 loopback HTTP。身份范围必须覆盖发现、提交、按键查询、状态、事件及文件读取，不能凭一个 UUID 访问其他调用方的数据。Eyes 的内部令牌不转发给 Agent。

## 4. 能力发现

`AgentCapabilities` 包含：

- `agent_id` 与 `agent_version`：接入端身份和可确定的版本；版本不明确时显式为 null。
- `input_schema`：业务输入的 JSON Schema 2020-12 对象；无额外约束时也应明确声明 `{"type":"object"}`。
- `max_concurrency`、`session_isolation`、`environment_isolation`：目标可兑现的共享容量及隔离边界。并发大于 1 要求两种隔离均成立。
- `cancellation`、`resources`、`events`、`artifacts`：可选端点是否可用。不支持的能力返回 false，对应操作返回明确的 `unsupported_capability`。
- `terminal_retention_seconds`：终态记录、去重记录及已发布结果/产物至少保留的秒数，最少 86400 秒。

幂等提交、按键查询和状态查询是核心要求，不作为可关闭的能力。一个只能临时调用函数、进程退出就丢失全部状态的服务不符合这个核心协议。

接入端还必须自行限制活动任务容量，多个 Eyes Runner 或其他客户端共同访问时不能超额。Eyes 的实验、项目和全局额度继续生效；能力声明不替代接入端的容量控制。能力或版本变化需要重新发现并发布目标版本；不能改写已冻结实验快照。

## 5. 任务、身份与幂等

`AgentTask` 包含以下字段：

| 字段 | 约定 |
| --- | --- |
| `task_id` | 对应逻辑测试任务，重试业务执行时可以保持不变 |
| `attempt_id` | 一次业务执行的唯一身份；新的业务执行必须使用新 ID |
| `idempotency_key` | 同一执行的传输重试复用原键；不得用新键盲目重试响应丢失的提交 |
| `deadline` | 带时区的绝对截止时间；重传不能重新获得一整段超时时间 |
| `input` | 符合已发布 `input_schema` 的业务输入 |
| `resources` | 已上传且当前身份有权读取的输入文件引用，名称在任务内唯一 |
| `traceparent` | W3C 格式的执行上下文，关联追踪，不替代业务身份 |

`run_id` 由接入端生成并稳定保存，一个调用方的一次 `attempt_id` 只能关联一个运行。同一 `attempt_id` 换键重复提交也必须拒绝为冲突，不能开启第二次业务调用。

接入端先校验请求、权限、资源、截止时间与容量，再原子保存请求、幂等映射和执行意图，成功持久化后才能返回接受响应。业务执行只能在记录接受之后开始；崩溃后不得因为“不记得返回过什么”而重新执行未知任务。

相同身份、相同键、相同结构化参数返回原 `run_id` 及当前快照；同键不同参数返回 409 `idempotency_conflict`。对象键顺序不影响比较，数组顺序影响比较，时间按同一 UTC 时刻解释，可选字段按本协议默认值解释。接入方不得通过简单比较原始 JSON 字节误判重传。

网络断开或响应丢失时，Runner 先按原键查询。查询也失败时保留未确认状态；在核心幂等保证有效的前提下才能重发同一个请求，不能创建新 Attempt 或新键。404 仅表示当前身份下没有可返回的记录，不证明远端从未执行过。

活动及 unknown 运行的记录不得按终态保留期删除。已完成记录最早在 `max(deadline, completed_at + terminal_retention_seconds)` 后过期；有过期标记时查询返回 410 `record_expired`。去重记录过期后的原请求已超过 deadline，提交必须拒绝，不能重新执行业务。截止时间已过但去重记录仍在时，可返回原结果。

## 6. 状态与结果

正常流程是 `accepted → queued → running → succeeded / failed`，可以省略 queued。运行中可以进入 cancel_requested。取消或超时只有确认任务及其副作用执行已经停止后，才能写为 cancelled 或 timed_out。

- `accepted`：请求已持久化，尚不代表调用 Agent。
- `queued`：等待接入端自己的执行资源。
- `running`：已开始执行。
- `cancel_requested`：已请求停止，仍未确认结束。
- `succeeded`：执行已结束并具有结构化 output；不表示评分通过。
- `failed`：有明确执行失败事实且已停止；需要错误原因。
- `cancelled` / `timed_out`：已确认停止，需要完成时间。
- `unknown`：执行结果无法确认，需要原因；不能自动当作失败或安排新的业务执行。

`AgentRun` 带递增 `revision`、`observed_at` 以及当前结果。结果只在终态或 unknown 时出现，必须匹配快照的 run_id 和 status。客户端丢弃旧 revision；对同 revision 的冲突内容记录协议错误，不自行选择较新的网络响应。

`AgentResult` 将 `output`、执行错误、`stopped_confirmed`、`completed_at`、清理状态、证据状态及产物分别表达。四种明确终态都要求已确认停止和完成时间。unknown 不填写已确认的结果完成时间，但可以单独报告“已知停止、结果仍丢失”；停止事实不等同于业务成功事实。

对于停止未确认的 unknown，Eyes 必须保留相应执行额度。已确认停止但结果未知的情况，只能通过明确核对路径释放额度，同时保留未知结果，不能伪造成功或失败。当前客户端支持有效租约内查询，控制端尚无重启后的自动核对；内部 unknown 继续保留额度，需要显式核对。

明确终态的结果不可覆盖，重新执行生成新 attempt/run。unknown 后若获得可靠事实，可以提升 revision 转为确定终态，并保留原观察与核对来源。证据后补不能覆盖旧结果引用的证据或旧评分，应走补充证据及显式重新评分流程。

## 7. 取消

重复取消同一个 run 不创建新工作。202 表示请求已接受但停止尚未确认，200 表示返回已确定结果；两者都返回 `AgentCancelResult`。

`accepted` 与 `stopped_confirmed` 是独立字段。已接受取消的运行应成为 cancel_requested、unknown 或明确终态；不能回复 accepted=true 却仍提供没有取消记录的 running 快照。停止确认必须与返回的运行结果一致。

取消可能与正常完成竞争。如果任务已成功完成，应返回原 succeeded 结果，不能改为 cancelled。接入端只有确认远端业务执行及相关后台任务停止，才能声明 stopped_confirmed；本地连接关闭、子进程退出或 API 返回“已收到请求”都不足以证明远端已停止。

## 8. 输入资源与输出产物

资源为可选能力。上传使用调用方生成的 UUID：`PUT /agent/v1/resources/{resource_id}`，请求头提供 `Content-Type`、`Content-Length`、`X-Eyes-Resource-Name`（UTF-8 百分号编码）和 `X-Eyes-SHA256`。接入端校验完整字节数和 SHA-256 后才发布可引用的资源，返回对应 `AgentResource`；同身份同 ID 同元数据/字节重传返回原引用，冲突返回 409。

资源与认证身份绑定，提交任务时再次验证引用的名称、大小、摘要和访问权。name 仅是逻辑名称，不直接作为可越界的文件路径。资源可以在提交前上传，未绑定资源的保留期限由接入端公开配置；已接受任务的输入在任务结束前不得被删除。没有完整上传确认时，不能把它作为已就绪资源使用。

协议不发送 Runner 的宿主机绝对路径，也不要求目标能访问 Eyes 的本地磁盘。输入业务数据不能包含模型密钥；模型凭据由 Agent 环境提供。v1 不支持任意远程 URL 拉取，避免把下载授权和模型输入混为一体。

结果中的每个 `AgentArtifact` 包含 artifact_id、name、media_type、size_bytes 和 sha256。下载路径由 run_id 与 artifact_id 构成，客户端不跟随任意重定向。Eyes 完整校验字节数和摘要后保存到自己的证据存储，并生成内部 Artifact ID；不能直接把外部引用当作已入库证据。下载失败保持证据缺口，不能静默跳过后继续声称完整。

不支持资源/产物的目标仍可参与结构化输入输出评测；包含文件要求的数据集在派发前明确判为不兼容，不伪造文件或通过结果。

## 9. 事件与证据

事件按 run_id 分流，每项包含稳定 event_id、运行内递增 sequence、带时区的 occurred_at、type 和 data。不同运行不共享 sequence；接入端负责给多个内部生产者汇总后的流排序，并保留内部来源信息。

分页 cursor 不透明且可重放。同一事件重传保持 ID 和内容不变；相同 ID 不同内容属于协议冲突。事件按 sequence 返回，每页最多 200 项。只要还可能有后续事件，就返回可用于继续查询的 next_cursor，即使本页为空；已经结束且没有后续事件时才返回 null。

标准事件封装可以携带目标原生事件，私有 type 使用 `custom.<namespace>.<name>`；不得把仅有模型提出调用的消息标成已真实执行的工具结果。更细的模型/工具语义事件需在后续契约中定义后才能声明支持，v1 不声称能自动还原任意 Agent 内部执行图。

`AgentEvidence` 独立报告 collecting、sealed、partial 或 unavailable；dropped_events 不知道时为 null，不能填写 0。sealed 要求已声明范围内采集结束且丢弃数为 0，不表示拥有全部内部行为。结果与事件页都保留证据状态；网络重试成功不能消除原本的采集缺失。

## 10. 错误与运行恢复

错误消息统一为 `AgentError`。错误码应稳定，message 为有界且脱敏的人类说明。

| HTTP 状态 | 常用错误码 | 客户端行为 |
| --- | --- | --- |
| 400 | `unsupported_protocol` / `invalid_request` | 修正协议或格式，不启动业务重试 |
| 401 / 403 | `unauthenticated` / `forbidden` | 修正凭据或范围，不重复派发 |
| 404 / 410 | `not_found` / `record_expired` | 记录缺失/过期，不能推断没有执行 |
| 409 | `idempotency_conflict` / `attempt_conflict` | 明确冲突，不生成新键绕过 |
| 413 | `payload_too_large` | 拒绝请求，不截断后继续 |
| 422 | `invalid_input` / `deadline_expired` / `unsupported_capability` | 修正输入或选择兼容目标 |
| 429 | `capacity_exceeded` | 未接受任务时明确返回，客户端按 Retry-After 延迟 |
| 503 | `temporarily_unavailable` | 提交是否生效不确定时先按键查询 |

接入端在重启后恢复原执行映射，查询到同一个 run_id；原业务是否运行不明时返回 unknown，不重放业务调用。协议要求持久化，但不规定必须使用哪一种数据库。没有这个保证的临时进程包装只能作为开发接入，不能标为符合核心协议。

## 11. 与当前 Eyes 的对应关系

| 当前内部数据 | 外部协议 |
| --- | --- |
| CaseRun ID | task_id |
| Attempt ID / idempotency_key / deadline | attempt_id / idempotency_key / deadline |
| 用例 input | AgentTask.input |
| 目标能力快照 | 发现结果经过验证后发布；不把 TargetPublish 或 Runner 配置直接发给 Agent |
| 外部 run_id | Attempt.remote_operation_id |
| ExecutionResult | 经协议状态、身份与停止事实校验后映射；不是直接复制未知 JSON |
| Event / Artifact / Manifest | 先认证、校验和持久化，再建立内部证据引用 |

现有 Python 和通用 HTTP 接入保留兼容。新接入优先使用统一协议客户端 `agent_http`；不会要求外部 Agent 安装 Eyes SDK。SDK 埋点是可选增强，不是参加基础评测的前提。

## 12. 落地顺序与当前证据

最初阶段完成独立数据契约、可导出的 JSON Schema 和 HTTP/状态语义。2026-10-10 新增 Runner 的 `agent_http` 客户端、发现发布命令、领取能力匹配、发布/实验兼容校验和 `eyes.agent_service.http.create_app` 参考服务。没有修改外部协议模型、Schema 或数据库，没有新增仓库测试、用例或模拟服务。

参考服务持久化请求、去重映射、运行快照、事件与文件，重启不重放未知业务执行；仅支持一个认证调用方和一个 POSIX 服务进程。客户端支持核心接口及按能力的取消、事件、资源和产物交换。外部 nullable 丢弃计数在内部旧整数契约中保留原值与证据缺口，详见运行时兼容说明。

真实 MewCode HTTP 回调已准备，调用原 Agent 事件循环而非预设输出；本次 Linux Docker 引擎启动崩溃、Eyes API 未开放，未实际完成发现、导入、执行、独立评分、证据或认证验收。MewCode 不声明取消/资源能力。两个不同实现的真实 Agent、可选能力及故障行为仍需补齐证据；本轮静态检查不能替代它们。

已有 [Deta/Zeta 实测](../integrations/zeta/README.md) 可以核对协议是否覆盖并发、准备失败、未知执行、取消竞争和代码产物，但它使用的是现有 Python 适配器，**不是本统一协议的端到端验证**。Pi 的原生 RPC 到本协议的转换也尚未实现。
