# 在 Agent 中工作，在 Eyes 中观测

> 自 2026-10-11 起仅在当前 Windows 宿主机开发，API 在本机 Linux 容器运行，启动方式见 [Windows/MewCode 说明](../integrations/mewcode/README.md)。2026-10-12 trae 的直接任务/被动 exporter 在独立环境通过本轮正向、补传、权限、Web 和按需重启范围，见[验收记录](observation-trae-acceptance-20261012.md)；Deta 及其他 exporter 不据此自动升级验收。

被动观测不需要测试集、评分器、实验或 Runner。用户在 Agent 中照常输入任务，Agent 保持执行与工具权限，Eyes 接收实际埋点事件并展示。下面 Deta 配置是该已有接入的专用说明。原有实验评测入口继续用于批量任务和评分。

## trae 直接任务入口

trae 当前已实现 `python -m trae_agent.observe` 直接用户任务及独立 exporter，复用它自己的模型/工具循环，不创建 AgentTask 或 Eyes 实验，不读取主动 HTTP events 来造观测。配置与 Docker Linux 命令见 [trae 接入说明](https://github.com/pretextQ/trae-agent/blob/main/docs/OBSERVATION.md)。当前默认 `mimo-v2.6-flash`；设置真实来源 URL/token、专用状态目录、明确预算，可按用户选择启用正文采集。API 不可达时有界 spool 保留，`--flush-only` 仅重传，不执行任务/模型；来源身份改变不复用旧 spool。

本轮事件显式 schema_version、稳定 run/session/event ID、递增序号和 UTC 时间；读取权限仍为项目级 read/manage，来源凭据只有本来源写入权，不能读取项目。来源内 external run ID 不等于服务端 ObservedRun UUID。完整实现/实测/失败/限制见[验收](observation-trae-acceptance-20261012.md)。

## 启动与接入

本机使用时，完成数据库迁移和项目初始化后运行 `uv run eyes-server`，在 Deta 中运行 `uv run --env-file .env deta -i`。Deta 默认连接 `http://127.0.0.1:8000`，不需要创建来源或填写令牌；首次事件自动登记本机来源。同一工作目录的来源标识保存在 `.deta/eyes/<配置摘要>/source-id`，只用于归组，不是认证凭据。

本地 API 若使用其他端口，只需在 Deta `.env` 设置 `EYES_OBSERVATION_URL=http://127.0.0.1:8001`。完整正文采集仍需 `EYES_CAPTURE_BODY=true`；设置 `EYES_OBSERVATION_ENABLED=false` 关闭采集。Web 的项目连接权限保持原有认证。

`eyes-server` 固定监听回环地址并默认开启本地观测，显式 `EYES_LOCAL_OBSERVATION=false` 可关闭。通用 ASGI factory 默认关闭本地入口；本机自定义 uvicorn 启动时需显式开启，并使用回环监听与 `--no-proxy-headers`。不要在反向代理后开启本地入口。接口校验直连 peer、Host，拒绝 Origin 和转发头。远程部署不会因为使用通用 factory 自动开放免令牌入口。

服务器只有一个项目时自动归入它；多个项目需由服务端设置 `EYES_LOCAL_OBSERVATION_PROJECT_ID`，不会猜测目标项目。本次本机环境已设置。任意本机进程可写入本地观测，因此它适合单用户开发环境。远程或多人共享环境使用下面的令牌接入。

远程接入：在 **Agent 观测 → 接入 Agent → 远程 Agent 接入** 创建来源，将返回的 `EYES_OBSERVATION_URL`、`EYES_OBSERVATION_TOKEN` 配入 Deta。提供令牌时继续使用认证上报；无令牌时 Deta 只允许回环地址。远程来源令牌只显示一次，仅允许上报，不能读取或管理项目。

页面每 2 秒拉取一次记录。一次终端输入对应一个任务；连续输入和恢复会话使用同一 session_id，任务 ID 独立。列表可点击会话筛选，详情按 Agent 轮次展示模型输入/响应、模型调用尝试、工具名称/参数/结果、耗时、token 用量和 trace/span 标识。工具输出是执行器返回的观测记录，不能单独证明外部副作用成功。

### 执行流程图与节点详情

运行详情默认显示流程图，可切换回事件列表。按轮次展示模型调用、模型响应、工具调用、上下文压缩和任务边界；同一次调用的开始与结束合并为一个节点。点击节点或轮次标题呼出详情浮层，再次点击同一节点收起，点击其他节点切换内容；也可用关闭按钮、Escape 或点击画布空白处关闭。画布始终占满可用宽度，浮层不挤压画布、没有阻挡节点点击的遮罩。浮层统一锚定节点正上方，底部尖角指向节点，并跟随画布移动与缩放；打开时必要的画布平移为详情留出空间，窗口边缘限制浮层宽度和高度。详情提供已上报的输入输出、工具参数、耗时、用量和可展开的原始事件（含事件 ID、序号及 trace/span 标识）。未采集正文或耗时时明确显示未提供。

画布支持平移、缩放、适应全部节点、定位等待结束的调用及错误、折叠已结束轮次。自动轮询保留视角与所选节点；加载后续事件时保留当前画布。窄屏采用纵向排列；跨越布局断点时重新设置初始视角。详情中的长 JSON 支持搜索、展开和复制。

图形是现有事件的展示，不改变执行状态、采集协议或数据库：

- 模型与压缩事件按当前任务内的轮次、trace_id 和 span_id 配对；工具事件按轮次及 tool_call_id 配对。重复标识造成歧义时保留独立节点。
- 模型输入输出仅在其 span 明确对应唯一模型调用的 parent_span_id 时并入该节点；否则独立展示。
- 虚线箭头表示记录顺序，不声称并行或因果关系。轮次标题可查看该轮的开始/结束记录。
- 收到结束事件显示“已结束”，不把 OTel 的 UNSET 解释为业务成功。只有工具结束记录时提示没有观察到开始；调用可能在执行前被拒绝。
- 后续分页未加载与已知观测缺失分别提示；没有结束记录的节点不凭任务结束或心跳中断推定成功、失败或停止。只有任务仍在运行、已加载全部现有事件、证据仍在采集且该轮未结束时显示“等待结束”。

前端实现位于 `frontend/src/lib/observation-flow.ts`（配对及展示状态）与 `frontend/src/components/ObservationFlow.tsx`（React Flow 画布、Dagre 排列和节点详情）。原有实验详情的事件浏览器不受此次改动影响。

默认不设置 `EYES_CAPTURE_BODY=true` 时只上报元数据。启用后会上传对话、模型上下文和工具输入输出到配置的 Eyes 服务；已知模型/观测密钥及常见敏感字段会替换，但不保证识别自由文本中的全部秘密。来源可在接入面板停用，停用不删除历史。

## 协议与状态

- 本机写入使用 `/v1/observation/local/events` 和 `/local/heartbeat`，携带 `X-Eyes-Local-Source` UUID 自动登记来源；停用后继续拒绝该来源，不自动重新启用。
- 公开接口前缀 `/v1/observation`：管理者创建/停用 `sources`，项目读者查询 `runs` 和 `runs/{id}`；来源令牌写入 `events`、`heartbeat?run_id=...`。
- `ObservationBatch` 和 `ObservationEvent` 定义于 `src/eyes/contracts/observation.py`，协议版本为 `1.0`。批次携带 Agent 自有 run/session ID，事件携带 event_id、任务内 sequence、时间、类型、轮次、工具与 trace/span 关联。单批最多 50 条，单事件最大 64 KiB。
- 服务端在 PostgreSQL 事务持久化后确认。同来源同 event_id 且内容一致的补传幂等；不同内容或序号冲突返回 409。观测任务不进入实验调度状态机。
- `completed/failed/cancelled/limited` 来自 Agent 终态；运行中超过 30 秒没有上报/心跳时查询显示 `disconnected`，只代表失去观测，不代表任务停止。
- `complete` 仅代表从开始到终态的已声明事件序列收齐且没有上报的截断/丢弃；缺少边界、序号有缺口或截断时为 `partial`。未结束且无已知缺口时为 `collecting`。它不表示所有内部过程可见。
- 轮次、模型尝试和工具调用分别统计；缺少 token usage 不当作零。传输补传不会重新执行 Agent。

## 缓冲与边界

Deta 后台发送器使用 256 条内存队列与工作目录 `.deta/eyes/<配置摘要>/pending` 的 64 MiB 有界磁盘缓冲，成功确认后删除；瞬时错误重试，永久 4xx 留在 `rejected` 并记录告警。正常退出会先尽力将剩余队列落盘，下次以相同 URL/来源令牌启动 Deta 会重放待发送文件。正文过大时截断并标记；队列/磁盘满时可能丢弃并形成不完整记录。强制杀进程或磁盘写入失败仍可能丢失尚未落盘的数据。

当前 exporter 接入 Deta CLI 的 Agent 事件和 OTel 模型边界；直接在 Python 中创建 Agent 不会自动启用 exporter。任务外的手动压缩不归入某个任务。没有采集逐 token 流、屏幕录制、隐藏推理、工具进程的全部系统调用，也不承诺任意 Agent 零改动接入。一个工作目录、同一来源只允许一个 exporter 进程持有发送锁。

观测正文当前保存在 PostgreSQL JSONB；备份应包含数据库。现有实验 Artifact 清理不会删除这些观测表，尚无观测记录自动保留清理策略。不能据此宣称生产容量或长期保留已验收。
