# 在 Agent 中工作，在 Eyes 中观测

2026-10-13 可选容量保护已实现：`EYES_PROJECT_EVENT_CONTENT_BYTES=0` 默认关闭，正数限制每项目已保留实验事件与观测事件的 JSON 文本字节总量；公共与 local 观测入口均检查，超额整批 507/回滚，原已接受内容重传保持幂等，冲突/410 语义不变。失败不更新任务终态或把缺失事件显示成完整证据。容量释放后发送端须重传原待确认批次，服务端不恢复客户端已丢弃的数据。管理员在 `GET /v1/operations/capacity` 或 `eyes-ops capacity --project-id UUID` 查看用量、阈值、时间及按稳定 ID 去重的当前告警。额度不是 PostgreSQL 磁盘上限，正文清理后审计封装仍占额度；配置/锁与未覆盖对象见[运维说明](platform.md#容量保护与当前告警)，真实材料副本结果见[容量验收](capacity-protection-20261013.md)。

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

观测正文保存在 PostgreSQL JSONB，备份必须包含数据库。自 0006 起，观测保留策略复用 `eyes-ops maintain` 与 Compose maintenance；它独立于实验 Artifact 保留期。副本清理、权限与页面的实际结果见[生命周期验收](observation-retention-20261013.md)。

## 观测保留与清理

默认 `EYES_OBSERVATION_RETENTION_DAYS=0`，不按年龄标记或清除现有观测。启用时必须给出项目 UUID：`EYES_OBSERVATION_RETENTION_PROJECT_ID`，或命令的 `--project-id`（优先于环境配置）。一个自动维护进程对应一个明确项目；不同项目可按需运行同一命令，不隐式扫描全部项目。

只有来源报告了 `completed/failed/cancelled/limited`、存在 terminal_sequence 的任务可到期。以**服务端终态首次接收时间 terminal_received_at 与最后事件接收时间 last_seen_at 中较晚者**计算保留天数，两者都严格早于本轮 UTC cutoff 才清理；不使用 Agent 的 occurred_at、metrics.ended_at 或创建时间单独判定。迟到补齐或原样重传延后清理。历史终态用 `max(created_at, last_seen_at)` 保守回填 terminal_received_at；缺少明确终态的历史记录继续保护。

running 永不自动清理。disconnected 是 running 的查询展示状态，30 秒失联、撤销来源或 exporter 退出均不证明 Agent 停止，不能使它获得清理资格。当前不提供强制删除未结束任务的命令或停止确认接口；等待可信终态，无法得到时保留并由接入方核对，人工确认/长期失联生命周期仍是后续目标。

在 Windows PowerShell 中配置保留期；API/运维进程按既有 Docker Linux 部署运行。以下以已部署 Compose 为例，替换真实项目 UUID，先预览再执行：

```powershell
# 写入 deploy/.env：EYES_OBSERVATION_RETENTION_DAYS=30
$observationProject = 'PROJECT_UUID'
docker compose --env-file deploy/.env -f deploy/compose.yaml run --rm --no-deps api eyes-ops maintain --observations-only --project-id $observationProject
docker compose --env-file deploy/.env -f deploy/compose.yaml run --rm --no-deps api eyes-ops maintain --observations-only --project-id $observationProject --apply
```

省略 `--observations-only` 时沿用现有实验证据和文件维护，同时处理配置项目的观测；`--attempt-id` 只处理原实验 Attempt，不清理观测。运维 CLI 使用部署者的数据库权限，无来源令牌或项目令牌删除入口。project read/manage 的项目读取范围、来源令牌仅写入本来源的边界保持。

| 配置 | 默认 | 允许范围 | 含义 |
| --- | --- | --- | --- |
| `EYES_OBSERVATION_RETENTION_DAYS` | 0 | 0～36500 | 0 不标记新的过期任务；正数为完整 UTC 天数 |
| `EYES_OBSERVATION_RETENTION_RUN_BATCH` | 20 | 1～100 | 每批最多标记的任务数 |
| `EYES_OBSERVATION_RETENTION_EVENT_BATCH` | 500 | 1～2000 | 每批最多清空正文的事件数 |
| `EYES_OBSERVATION_RETENTION_MAX_BATCHES` | 10 | 1～100 | 每轮最多独立事务批数；预览只查看一批 |

预览的 observations.runs/events 是**一批候选**，不是全项目到期总数。执行每批独立提交，标记任务过期、清空 prompt、保存清理理由/保留天数/cutoff/原完整性及事件数，再有界清空事件 content。事件 ID、sequence、原 digest、接收时间与任务身份/终态/历史数值统计保留。数据库触发器仅允许过期清空转换，不开放任意事件更新。

查询用 `FOR UPDATE SKIP LOCKED` 跳过竞争行，观测清理只取备份共享维护锁，不持有调度锁或全局独占锁。每批 lock_timeout=2 秒、statement_timeout=15 秒，错误使当前批回滚、命令退出 3；此前已提交批次保留，可重复执行。`batch_limit_reached=true` 表示最后一批达到至少一个处理限额，继续执行以排空；即使为 false，竞争锁也可能使本轮跳过候选。禁用年龄策略不会恢复过期正文，指定项目仍可排空此前已标记的正文。

任务标记提交后，API 详情立即返回 `evidence_status=expired`、expired_at、expiration_summary、空 events、has_more=false；项目列表仍保留任务摘要。不存在/跨项目保持 404；原已过期 run 重传返回 410 observation_expired，不重新接收正文。Web 列表标明“观测内容已过期”，详情移除任务正文与流程图，历史统计不能作为当前完整证据。分批未排空的数据库正文暂存不对 API 暴露；已被客户端下载的副本不能远程撤回。

自动执行：在 deploy/.env 同时写保留天数和项目 UUID，显式启用既有 profile：

```powershell
docker compose --env-file deploy/.env -f deploy/compose.yaml --profile maintenance up -d maintenance
```

既有维护进程每小时执行 `maintain --apply`，每轮仍受批数限制；不新增调度服务。interval 循环响应 SIGTERM/SIGINT，完成当前轮后退出；Compose 给维护进程 3 分钟停止宽限。若显式提高 max_batches 或旧实验证据维护耗时超出宽限，仍可能被强杀；已提交批次可续清，不能把停止进程理解为数据库全部排空。多项目手工维护可以覆盖配置中的 UUID。清理和容量不同：审计行、活动/失联任务、数据库页/WAL、备份与客户端副本仍占空间。VACUUM 可回收供数据库复用，普通清理不保证文件立即缩小或安全擦除磁盘。项目事件正文额度与产物卷空间拒收、当前告警已新增，见本文开头；数据库物理硬容量限额、大规模积压吞吐与长期趋势仍未实现/验收。备份、升级及不能丢失过期标识的降级规则见[平台说明](platform.md#观测迁移与备份恢复)。
