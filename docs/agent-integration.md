# Agent 接入与 Runner

当前源码提供通用 HTTP 接入、本地 Python 接入、独立执行与评分进程、SDK 采集，以及通过认证 API 领取、续租和上报的宿主机 Runner。按本次要求，两个真实 Agent 的联调验收暂缓；这里的协议示例是接入说明，不能作为运行成功的证据。检查结果见 [验证记录](backend-validation.md)。

## 1. 启动宿主机 Runner

先按 [后端说明](backend.md) 启动 PostgreSQL、API 和 scheduler，然后在目标宿主机安装同一版本的 Eyes：

```sh
uv sync --frozen
cp deploy/runner.example.toml runner.toml
uv run eyes-runner --config runner.toml plugins
uv run eyes-runner --config runner.toml status
```

在控制端签发 Runner 令牌，令牌必须允许相应目标版本和工作类型：

```sh
uv run eyes-admin issue-token --project-id "$PROJECT_ID" --role runner \
  --target-id "$TARGET_VERSION_ID" --work-kind execute --work-kind score
```

把一次性输出的令牌通过本机环境变量 `EYES_RUNNER_TOKEN` 提供，然后启动：

```sh
uv run eyes-runner --config runner.toml run
```

`run --once` 最多领取一个执行工作和一个评分工作，等待已领取工作结束后退出。它不会等待整个实验完成：执行结果提交后新产生的评分工作可能要在下一次运行领取。持续运行使用普通 `run`。

配置中的 `execution_slots` 与 `score_slots` 独立限制本机容量。令牌只允许执行时把 `score_slots = 0`；只允许评分时把 `execution_slots = 0`。同一凭据对应一个服务端 Runner 身份；多个 Runner 使用不同令牌和 `state_dir`。文件锁阻止两个本机进程同时使用同一个目录。

所有路径相对于配置文件。模板复制到项目根目录后，默认状态目录为 `data/runner`。容器中的 `localhost` 指容器自身；宿主机 Runner 的地址按实际 API 和 Agent 网络设置。当前 Compose 部署控制端，Runner 在目标宿主机独立运行。

## 2. 通用 HTTP 接入

HTTP 适配器只声明 `task` 观测范围：任务输入、输出、HTTP 调用边界、异常和耗时。它不解析外部服务内部轨迹、SSE 或任意框架的流式协议。需要内部模型和工具观测时，使用下面的本地 Python SDK 接入。

发布目标使用管理令牌向 `POST /v1/targets` 提交 `TargetPublish`。以下是配置结构；名字、地址、版本和隔离能力按实际服务调整：

```json
{
  "schema_version": "1.0",
  "name": "http-agent",
  "external_version": null,
  "capabilities": {
    "schema_version": "1.0",
    "adapter": "http",
    "session_isolation": true,
    "environment_isolation": false,
    "cancellation": false,
    "idempotency": false,
    "reconciliation": false,
    "observation": ["task"]
  },
  "config": {
    "url": "http://127.0.0.1:9000/tasks",
    "request_mode": "envelope",
    "response_mode": "output",
    "output_pointer": "/output",
    "request_timeout_seconds": 30,
    "max_response_bytes": 1048576
  },
  "secret_refs": {},
  "concurrency_limit": 1
}
```

将服务的 origin 加到本机 `allowed_http_origins`。规则按 scheme、host、port 比较；执行、取消及查询地址都必须被允许。禁止 URL 内嵌账号密码，禁止跟随重定向；默认不读取系统 HTTP 代理环境变量。

Runner 注册时上报规范化的 `http_origins`；服务端在领取前检查全部配置地址。即使凭据允许项目所有目标，也只会分配 origin 匹配的 HTTP 工作。本机准备阶段仍保留同一检查。

### 请求与响应

| 配置 | 行为 |
| --- | --- |
| `request_mode = "envelope"` | POST 完整 `ExecutionInput`，含任务 ID、幂等键、截止时间、input、environment 和目标快照；密钥仍为引用 |
| `request_mode = "input"` | POST 用例的 `input` JSON 对象 |
| `response_mode = "output"` | 2xx 返回 JSON，按 `output_pointer` 取一个 JSON 对象作为任务输出 |
| `response_mode = "result"` | 按 `output_pointer` 取完整 `ExecutionResult`，可明确报告业务失败、未知结果、证据缺口等 |

`output_pointer` 使用 JSON Pointer，例如 `/output/answer`；空字符串表示整个响应。输出必须是 JSON 对象，文本答案请包装为 `{"answer": "..."}`。HTTP 3xx/4xx/5xx、连接中断、响应解析失败都不能证明远端副作用未发生，执行意图之后按未知结果处理。

每个调用都携带 `traceparent`、`Idempotency-Key`、`X-Eyes-Attempt-Id` 和 `X-Eyes-Session-Id`。这些头由 Runner 控制。服务必须实际按 Attempt 隔离会话和业务环境，才能声明相应能力。发送幂等键不等于目标已经实现去重；Runner 不自动重发业务执行请求。

### HTTP 密钥

目标配置引用密钥，不提交明文头值。例如：

```json
{
  "secret_refs": {"agent_auth": "env:AGENT_AUTH_HEADER"},
  "config": {
    "url": "https://agent.internal/tasks",
    "secret_headers": [{"name": "Authorization", "secret_ref": "agent_auth"}]
  }
}
```

这是配置片段，合并进完整的目标发布请求。Runner TOML 中添加 `secret_env_allowlist = ["AGENT_AUTH_HEADER"]`，在本机环境提供完整头值，例如 Bearer 认证的头值。普通 `headers` 只放非秘密内容。`env:NAME` 之外的引用会被拒绝；平台 Runner 令牌不能暴露给目标或评分插件。

发布配置拒绝 `Authorization`、`X-API-Key`、`X-Auth-Token`、Cookie 等已知敏感字段及 URL 中的已知敏感查询参数，统一忽略字段大小写并将连字符转为下划线。服务端与 Runner 脱敏共用字段表。历史不可变版本不会被本次修改重写；字段规则也不能识别任意自定义名字下的秘密。

### 异步操作、取消和查询

接入异步服务时配置 `operation_pointer = "/operation_id"`、`reconcile_url`，并声明 `reconciliation = true`。202 响应必须包含远端操作 ID；Runner 立即保存并尝试更新服务端，随后按 `poll_seconds` 查询。没有可查询 ID/端点的 202 会形成 `unknown`。

查询端点接收 POST：

```json
{"attempt_id": "<attempt UUID>", "operation_id": "<remote ID>"}
```

仍在运行时返回 `{"state": "queued"}` 或 `{"state": "running"}`。已结束时返回完整 `ExecutionResult`，也可以包装成 `{"result": {...}}`。只有终态结果才结束轮询。同步服务也可配置查询地址，用于取消过程中的即时状态核对。

取消端点 `cancel_url` 接收 POST 的 `attempt_id`、`idempotency_key`、`operation_id`；只有返回 `{"stopped_confirmed": true}` 才证明停止已确认。服务只接受取消请求但未确认停止时，应返回 false。请求和查询端点都是本协议的 POST，不会推测现有服务的 GET、路径模板或其他协议；可在现有服务前增加业务桥接端点。

Runner 到达截止时间、收到取消或失去租约时停止等待并尝试取消/核对。关闭本地连接、杀掉 HTTP 客户端进程都不能证明远端停止；停止或结果无法核实时保持 `unknown`，控制端保留额度。Runner 只在当前租约生命周期尝试核对，重启后的未知任务需要维护者确认事实后调用管理端 `resolve`，不会自动重跑。

## 3. 本地 Python 接入

本机 TOML 配置可信入口；服务端目标只引用别名，不能指定任意 Python 模块：

```toml
[python_agents.my_agent]
entry_point = "my_agent.eyes_bridge:execute"
python = "/absolute/path/to/agent/.venv/bin/python"
import_paths = ["/absolute/path/to/agent"]
prepare = "my_agent.eyes_bridge:prepare"
cleanup = "my_agent.eyes_bridge:cleanup"
execution_scope = "external"
session_isolation = true
environment_isolation = false
cpu_seconds = 300
memory_bytes = 2147483648
```

该 Python 环境也需要安装**同一版本的 Eyes 及其运行依赖**，并满足 Python >=3.14。使用当前项目解释器时可省略 `python`。Agent 独有依赖安装到绑定的环境，Runner 不修改目标项目。

目标版本设置 `capabilities.adapter = "python"`、`config = {"agent": "my_agent", "parameters": {...}}`。Runner 注册时按 `python_agents` 别名上报本地能力；服务端领取前匹配别名、隔离、取消、幂等、核对和观测范围，并跳过不兼容工作。本机准备阶段再次检查能力。`parameters` 由桥接函数读取。

桥接函数的调用接口为：

```python
from eyes.contracts.target import ExecutionInput
from eyes.sdk import AgentContext


def execute(request: ExecutionInput, context: AgentContext) -> dict:
    # 接入现有 Agent 的真实入口；每个 request.attempt_id 使用独立会话。
    with context.span("agent.run"):
        output = agent.run(
            request.input,
            session_id=str(request.attempt_id),
            workspace=context.workspace,
        )
    return output
```

`agent` 是接入项目自己提供的实例或入口。这里说明签名，不提供模拟 Agent 实现。函数可为同步或 async，返回 JSON 对象或 `ExecutionResult` 实例；返回对象会作为成功输出，业务失败请明确返回 `ExecutionResult`。函数抛错时，进程范围内的任务可记失败；涉及外部服务的任务保守记未知。

`prepare(request, context)` 和 `cleanup(request, context)` 同样支持同步或 async；未配置时为无操作。prepare 仅准备环境，不得启动业务任务；真正执行发生在控制端确认 `running` 后。每项工作在独立 POSIX 进程组和工作目录中运行，但外部业务数据、远程会话及工具自身的副作用由接入方隔离。

`execution_scope = "process"` 只能用于所有工作都留在该进程组内的任务；目标不能创建脱离进程组的后台任务，也不能留下无法停止的远程操作。这种声明下，进程组停止确认可支持 cancelled/timed_out。默认 `external` 下，杀本地进程不证明远端任务停止。

外部任务可配置 `cancel` 和 `reconcile` 入口。取消函数接收同样的请求与上下文，返回 `True` 或 `{"stopped_confirmed": true}` 表示已确认停止；核对函数返回 `ExecutionResult` 实例/其 JSON 表示，未知或仍在运行返回 None。执行函数可检查 `context.cancel_event` 做协作取消；可通过 `context.remote_operation(operation_id)` 提前保存远端 ID。取消钩子可能与执行函数并发，接入方需保证共享状态的线程安全。

### SDK 观测与产物

- `context.span("tool.name", attributes={...})` 记录明确埋点的真实边界，嵌套 span 保留父子关系。
- `context.event("tool.result", {...})` 记录结构化事实，带生产者 ID、单调序号、发生时间和实际 trace/span 标识。
- `context.artifact("relative/path", name="result.json")` 在 cleanup 前快照工作目录内的普通文件。返回本地快照标识；服务端产物 ID 由上传登记产生，以证据清单为准。
- `context.secrets` 为只读映射，只包含目标已声明且本机允许的密钥。输入和 target.config 不包含解析后的密钥。

OTel provider 在每个工作进程内创建，不替换 Agent 的全局 provider。执行根 span 使用分配的 trace/span ID；评分根 span 使用独立上下文并 Link 到执行根。内部观察只覆盖显式埋点的边界，不会自动还原模型或工具行为。

后台队列、单事件大小和每项工作事件总量有界。采集失败、截断、队列溢出及未完成 flush 会进入 `evidence_details`，并将证据标为 partial；观测错误不会替换函数返回值或原始异常。普通 stdout/stderr 被丢弃，避免破坏进程协议或保存未知日志密钥；Python 输出字节计数可见，原生及子进程输出无法完整计数。需要保存的诊断事实请显式调用 SDK。

本地 Python 还会在执行返回后、cleanup 前自动快照用例 `artifact_requirements` 中列出的相对路径；文件明确不存在时记录 `artifact.missing`，已有文件无法读取、越界或超限则记采集缺口。HTTP task 适配器会在准备阶段拒绝非空文件要求；远端结果可先以结构化输出评分，文件采集使用 Python SDK 桥接。

产物路径必须在 workspace 内，限制数量、大小并校验 SHA-256。文件字节不会自动脱敏，接入方应在产物和用例输入中去除凭据及敏感内容。文本结果、事件和错误会掩码已知密钥字段和已解析密钥的字面值；这不能替代通用秘密识别。

## 4. 规则评分与本地 Python 评分

评分在独立进程运行，与执行任务使用不同容量。输入为 `ScoreInput`：冻结用例、执行结果、评分器版本/配置、固定证据清单、授权产物和服务端截止时间。评分插件不接触数据库，也没有管理端令牌。

评分领取响应仅包含 `ScoreAssignment`（评分、尝试、清单 ID 和计算截止时间）。Runner 使用当前身份与 lease token 调用 `POST /v1/work/{id}/score-input` 读取完整输入，核对这些固定字段后写入私有目录的只读 `payload.json`；子进程命令只传文件路径。该读取不持有全局调度锁。API 的 `EYES_MAX_SCORE_INPUT_BYTES` 与 Runner 的 `max_score_input_bytes` 默认均为 32 MiB，调整时应同步；超限明确返回错误，不截断证据。`max_message_bytes` 继续限制进程控制消息与返回结果，不限制文件中的完整评分输入。

### 内置 rules

`eyes-runner ... plugins` 输出当前实现 SHA-256，发布评分版本时使用对应 `implementation_digest`。rules 配置为 1..100 项 `checks`：

| kind | 配置 | 判定 |
| --- | --- | --- |
| equals | `pointer` + `value`，或 `expectation_pointer` | 输出 JSON Pointer 的值与配置/用例预期按 JSON 结构和类型严格相等 |
| contains | 同上 | 文本或集合包含预期值 |
| event | `type` + 可选 `data` 属性 | 已采集事件包含指定类型和属性；要求 sealed 且 dropped_events=0 |
| artifact | `name` | 清单包含指定名称的已上传产物；要求 sealed，未捕获且没有 artifact.missing 事实则证据不足 |

配置结构例如 `{"checks": [{"kind": "equals", "pointer": "/answer", "expectation_pointer": "/answer"}]}`。用例的 expectations 放对应预期值，输入按 [后端说明](backend.md) 的 JSONL 协议导入。未找到输出或预期路径时记 insufficient_evidence；不合法规则或比较类型记 error。空规则不能默认通过。

没有数值语义时，全部检查通过才 pass。声明 numeric 后，规则通过比例映射到声明的范围；方向 higher 时比例越高分越高，lower 时比例越高分越低，再按冻结的 threshold 判定。理由记录逐项结果，引用属于该清单的实际输入、输出、事件或产物。

### 可信 Python 评分器

```toml
[python_scorers.business]
entry_point = "my_agent.eyes_scoring:score"
import_paths = ["/absolute/path/to/agent"]
cpu_seconds = 30
memory_bytes = 536870912
```

接口为 `score(request: ScoreInput, context: ScoreContext) -> ScoreOutput`，支持同步或 async。`context.artifact(artifact_id)` 只返回清单授权的本地文件，Runner 在下载时校验大小和 SHA-256 并设为只读；`context.secrets` 是评分器单独获授权的密钥。普通缺失证据返回 insufficient_evidence，运行错误返回 error，不可把这些状态写成 fail 或零分。

发布时 `plugin = "business"`，使用 plugins 输出的摘要。每次评分在运行前核对摘要；默认摘要是入口函数所在源码文件的 SHA-256。多文件插件可在本机绑定显式设置 `implementation_digest`，由维护者根据完整构建产物生成并冻结；运行时只核对该已配置声明，不重新计算整个依赖环境。摘要不是依赖锁或远程模型快照，需与插件自己的发布管理配合。

所有 pass/fail 必须引用证据。后端再次校验引用属于清单、产物可读、分数范围和阈值一致性。重新评分通过 `POST /v1/attempts/{id}/rescore` 创建新 ScoreRun，保留旧记录；不会重新调用 Agent。

## 5. 超时、恢复与本地状态

Runner 使用服务端 deadline 控制墙钟超时；心跳只续租，不延长任务截止时间。Python 绑定支持 CPU、地址空间和文件大小限制，使用 POSIX resource 接口；操作系统不支持的设置会使准备失败，不会假装限制已生效。进程组采用 SIGTERM 再 SIGKILL，最后检查进程组是否仍存在。独立进程用于依赖与故障隔离，可信插件仍具有宿主机权限；系统权限和网络边界由部署环境约束。[Python subprocess 文档](https://docs.python.org/3/library/subprocess.html)说明了 POSIX 会话和进程控制机制。

评分计算仍在 deadline 停止。工作进程在评分返回时写入 `ScoreOutput.completed_at`，随后关闭采集与进程；控制端允许在 deadline 后最多 `EYES_SCORE_SUBMISSION_GRACE_SECONDS`（默认 60 秒）提交按时计算的结果或超时/错误诊断。提交仍要求有效租约；过期提交、迟算完成结果和旧领取令牌均被拒绝。API 与 scheduler 必须使用相同宽限设置；调度扫描在租约失效或提交窗口结束时记录 error，不提前覆盖正在提交的超时诊断。时间戳来自可信 Runner，宿主机时钟应与控制端同步。

清理有独立期限和状态；清理失败保留工作目录，并保留原任务输出。执行中的强制停止通常无法再运行 cleanup，清理状态记 unknown。进程组停止未确认时记 unknown 并保留目录；评分进程无法确认停止时保留本地隔离标记，需维护者排查。

本地结构如下：

| 路径 | 内容 |
| --- | --- |
| `work/<work-id>/assignment.json` | 原领取响应、原 lease token 和冻结任务 |
| `payload.json` | 子进程读取的完整输入，私有目录内只读文件 |
| `intent.json` / `execution.json` | 执行意图记录 / 已返回的执行事实 |
| `result.json` / `ack.json` | 完整上报载荷 / 服务端确认接收记录 |
| `workspace/` / `capture/` | 隔离目录、事件、产物快照和采集计数 |
| `quarantine.json` | 中断、未知执行或清理异常的保留原因 |
| `outbox/pending/` | 等待确认的事件、产物和结果 |
| `outbox/rejected/` | 服务端永久拒绝的原上报及错误码 |

本地 JSON 和产物先写临时文件、fsync，再原子替换。业务结果先保存 journal，再加入有界磁盘 outbox；空间不足保留 journal，后续轮询或重启继续尝试入队。outbox 达到 75% 时暂停领取新工作，活跃任务继续停止、记录和上报。网络错误、408/425/429/5xx 保留原载荷重传；401/403/409/422 等进入 rejected，不修改原提交来绕过身份、领取令牌或幂等校验。

完成结果与证据上传使用各自的发送锁。通用 flush 优先发送完成结果，单项任务完成时只发送结果；证据上传失败或等待重试不会占住结果发送锁。执行封存前的证据等待仍按下述期限进行，上传缺口不能被当成完整证据。

产物登记按 Attempt 和完整元数据产生稳定 UUID，同元数据的登记重传复用 pending/ready 记录；内容上传仍校验大小和摘要。事件复用原 event_id，完成上报复用原 lease token 和结果载荷。结果重传与业务执行重试有独立含义，Runner 不因重启或失联重跑任务。

执行结束后等待最多 `evidence_wait_seconds` 上报证据，再封存结果；尚未确认的上传、永久拒绝和采集缺口标为 partial。晚到证据由后端生成新清单，不覆盖已有评分；需要显式 rescore 纳入新清单。此期限用于 Runner 封存前等待，不是服务端自动调度补齐策略。

重启只恢复已持久化事件、产物和完整结果。没有完整结果的工作保留隔离记录，等待服务端租约扫描与显式核对；即使 execution.json 中保存了输出，也不推测 cleanup 或停止情况。子进程检测到父进程管道关闭会尝试终止本地进程组；系统崩溃、脱离进程组的子进程和远程副作用仍需核对。不会根据保存的 PID 杀进程，避免 PID 复用误杀。

`status` 显示 pending、rejected、保留工作和隔离工作数量。正常执行目录在完成确认后回收；未知/清理异常目录和评分 trace 保留供排障。每项采集和 outbox 有界，历史保留目录的总量仍需部署者设置保留策略，首版不提供自动历史清理。目录包含任务输入和租约信息，使用私有权限，维护者应按敏感运行数据管理。

## 6. 兼容性与验收边界

此前给 `ExecutionResult` 增加可选 `evidence_details`，给 `ScoreInput` 增加可选 `execution_root_span_id` 和 `deadline`，给 `ExecutionInput` 增加可选 `artifact_requirements`。本次审查修复增加注册字段 `python_agents/http_origins`、结果字段 `completed_at`、契约 `ScoreAssignment` 和读取完整评分输入的接口，改变评分领取 payload 的结构。它们使用已有 JSON 字段和截止时间，不需要数据库迁移。协议仍是未发布原型的 1.0，控制端、scheduler 与 Runner 必须同步升级到本源码版本。旧注册缺少别名或 origin 时，不会获得相应 Python/HTTP 工作；持有额度时不能改变注册能力，应在升级前结束或核对旧工作。

已实现的通用接口不意味着目标已通过验证。HTTP/Python 两个真实 Agent 的完整执行、评分、证据查询以及 PostgreSQL 并发、故障和恢复验收按用户要求暂缓。前端已有实现与未连接状态的浏览器验证，见 [前端记录](frontend.md)。回归报告、CI 质量门槛、完整保留删除和部署验收仍属于后续工作。
