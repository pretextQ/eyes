# 统一 Agent HTTP 运行时

2026-10-10：客户端与持久化参考接入服务已实现，通过源码规范、格式及字节编译检查；Docker 恢复后真实 MewCode HTTP 基本闭环已完成，3/3 执行和独立评分通过。实际版本、事件/产物、认证及首次失败见[验证记录](agent-http-validation.md)。本页通用命令是接入步骤，不能将单目标验收推广到任意 Agent 或全部故障行为。

## 发布并执行统一协议目标

外部服务实现[协议 v1](agent-protocol.md)。在接入服务和 Runner 使用独立的 Agent Bearer 凭据，Runner 将该环境变量列入 `secret_env_allowlist`；Eyes 管理、Runner 和模型凭据不得复用。远程使用 HTTPS；loopback HTTP 只用于同机调试。Runner 不跟随重定向，不读取系统代理配置。

先发现实际能力，保存不含秘密的发布请求：

```sh
uv run python -m eyes.adapters.agent_http http://127.0.0.1:19045 \
  --name my-agent-v1 --token-env AGENT_HTTP_TOKEN > data/agent-target.json
```

使用项目管理身份将该文件 POST 到 Eyes `/v1/targets`。发现结果完整冻结在 `config.discovery`；`adapter` 为新增的 `agent_http`，其余使用现有 `TargetPublish`。服务端校验外部版本、能力、并发及密钥引用与发现快照一致，Runner 在每个工作 prepare 时再次实际发现；发生变化必须发布新目标版本。普通 HTTP 的配置不能直接改名迁移。

Runner TOML：

```toml
allowed_http_origins = ["http://127.0.0.1:19045"]
secret_env_allowlist = ["AGENT_HTTP_TOKEN"]
execution_slots = 1
score_slots = 1
```

按现有[接入流程](agent-integration.md)导入 JSONL、发布独立评分器、创建实验、签发只授权新目标的 Runner 凭据，再运行 `eyes-runner --config runner.toml run`。控制端、Scheduler 和 Runner 使用包含本实现的版本；新 Runner 注册 `http` 和 `agent_http`，旧 Runner 不会领取新 adapter 的工作。不改变旧注册或旧目标行为。

Runner 的安装环境也必须升级到相同版本，不能仅通过 Supervisor 的 PYTHONPATH 覆盖源码：隔离子进程有意不继承该变量，仍从其解释器安装的 Eyes 包加载 worker。MewCode 首次实际部署因此准备失败，完整安装代码同步后恢复；不要为此放开平台凭据环境隔离。

客户端只发送 `AgentTask` 的任务/尝试身份、原幂等键、原截止时间、业务 input、资源引用和 traceparent；不会发送预期答案、评分配置、Eyes 凭据或完整目标快照。`environment` 尚无外部 v1 表达，非空时在实验创建前明确拒绝，应由接入方的版本化准备逻辑消费业务 input。不支持产物的目标遇到产物要求也在创建实验前拒绝。

提交响应丢失或 5xx 后先按原键查询；仅按键查询明确返回 404 且截止时间未过时，最多重传一次完全相同的请求。查询失败/410/冲突或仍无法确认时保留 unknown，不生成新键或新 Attempt。404 本身不证明未执行，重传安全性来自协议要求的持久化去重。明确 4xx 不重发；429 本轮保守结束并保留诊断，不实现自动容量重试。状态和结果的身份、revision、状态转换、终态不可变性及结果一致性都检查。协议同 revision 的完整快照必须一致，包括 observed_at。

按能力读取取消、事件、资源和产物端点。取消响应中的完整运行快照经校验并交给现有 Supervisor 核对结果，保留与取消竞争的成功事实。关闭连接和本地进程退出不证明目标停止。重启后的平台未知任务自动协调仍属于后续任务，本轮没有实现；管理端显式 resolve 仍是核对路径。

## 证据交换

事件保存为内部 `agent.event`，source 为 `target_trace`，原 event_id、run_id、sequence、occurred_at、type 和 data 放在 data 中。内部事件有 Eyes 的 Attempt、trace 和采集来源，外部事件不伪装成 SDK 已执行工具事件。SDK 的 source 参数为新增可选项，旧调用缺省仍为 sdk。分页按 cursor 重放，并验证事件身份、排序、同 ID 内容冲突；每次请求 10 条、每工作最多去重 10000 条（只缓存摘要），响应及 Runner 缓冲继续有界。采集/下载失败、未结束的事件流和必要产物缺失均产生 partial，不宣称 sealed。重试成功不会删除此前记录的采集缺口。

产物仅从固定的 run/artifact 路径下载，校验大小和 SHA-256 后交给现有 `AgentContext.artifact`、outbox 及控制 API 登记；外部 ID 不作为内部已持久化证据 ID。文件名是逻辑名称，Runner 用自己生成的路径保存字节，不拼接外部文件路径。评分仍由现有独立进程读取固定内部证据清单。

输入资源可从数据集 input 的字符串字段提取，配置形式如下；仅在发现 `resources=true` 时可用：

```json
{"resources": {"document.txt": {"input_pointer": "/document", "encoding": "utf8", "media_type": "text/plain"}}}
```

合并到发现生成的 `config` 后发布；`encoding` 还支持 `base64`。上传校验返回的名称、UUID、大小与摘要后才提交资源引用。字段仍在业务 input 中，接入方自行定义其业务 schema；不会发送宿主机路径。上传失败属于准备失败，不启动任务。未绑定上传的保留策略由接入端负责。

外部 `dropped_events=null` 无法直接写进旧内部整数契约，因此内部保留非 sealed 状态并在 `evidence_details.agent_evidence` 保存原 null；内部整数仅统计可知计数，不能把它解释为外部零丢失。这个兼容映射没有修改公共契约或 Schema。

## 可复用的参考 HTTP 接入服务

`eyes.agent_service.http.create_app` 是真实后端回调的 HTTP/持久化外壳，没有默认 Agent、预设输出或模型行为。接入方自己的 factory 传入：

- `database`：私有 SQLite 文件路径；`bearer_token`：至少 32 字符的独立随机凭据；`capabilities`：真实 `AgentCapabilities`。
- `validate_input(input)`：按发布的 input_schema 校验输入，无业务副作用；不允许在此启动 Agent。
- `execute(task, context)`：同步或 async，实际调用 Agent 并返回属于 `context.run_id` 的 `AgentResult`。
- 可选 `cancel(task, context)`：同步或 async，重复调用必须安全；返回具有真实停止/结果事实的 `AgentResult`，或未确认时返回 None。必须与 cancellation 能力一致。

使用 `uvicorn my_integration:app --factory --host 127.0.0.1 --port 19045 --workers 1 --no-access-log` 运行。参考服务当前仅支持 POSIX，使用进程文件锁保证一份存储只有一个服务进程，不能配置多个 Uvicorn worker。一个存储绑定一个认证调用方，全部任务/资源/产物接口都要求同一 Bearer 身份；需要多调用方时接入方应部署独立存储/实例，或自行实现按调用方隔离的协议服务。

参考服务原子保存 task、幂等键、attempt 映射和接受快照后才提交回调；同键同参数返回原运行，同键不同参数和同 attempt 换键返回 409。时间归一为 UTC、补齐默认值、按结构比较。活动/停止未确认 unknown 一并占用接入端容量。服务崩溃重启后不重放业务，未完成记录转 unknown 并保留映射。读取仍返回原 run_id。

`context.event(type, data)` 持久化事件；`context.resource(ref)` 读取已确认的输入字节；`context.artifact(name, bytes, media_type)` 校验并持久化产物。结果只能引用本运行已发布的产物。参考限制为单事件 64 KiB、10000 事件、每运行最多 100 产物、单文件 32 MiB；限额损失进入证据状态。接入方负责事件语义、脱敏、deadline、工具与后台任务停止确认、隔离和清理；回调异常保守转 unknown，异常文本不返回调用方。

参考服务无限期保留记录、资源及产物，不自动过期或回收，满足终态最短保留期但需要部署者规划磁盘容量和备份。资源与结果均在同一私有 SQLite 存储，避免文件已写而映射未确认；输入文件名不用于磁盘路径。SQLite 仅用于外部接入端的单机协议状态，Eyes 控制端仍为 PostgreSQL，**没有平台数据库迁移**。接入端状态文件新增独立数据库，不触及 Eyes 的 0001～0004。

可靠的后端人工核对可通过接入方进程内 `app.state.resolve_run(AgentResult)` 追加 unknown → 确定结果；没有开放无认证 HTTP 修改入口，也不实现后台自动重跑。原明确终态保留，竞争回调不覆盖它。恢复文件锁后仍有外部执行存活时，接入方必须核对真实业务事实再解除 unknown。

MewCode 的真实回调见 [http_service.py](../integrations/mewcode/http_service.py) 与[启动说明](../integrations/mewcode/README.md)。是否完成真实验收只以验证记录为准。
