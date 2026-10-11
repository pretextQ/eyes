# 未知远端任务的安全自动核对

2026-10-11（Asia/Shanghai）：本任务实现了统一 `agent_http` 目标的重启后只读核对。代码检查通过，真实故障验收阻塞，**M2 未完整通过**。此前 `18381e4` 的记录只证明真实 MewCode 基本闭环、幂等查询及已完成 Agent 服务重启保持终态，不证明活动 Runner 崩溃恢复。

## 能力边界

只有冻结目标使用 `agent_http`、声明 reconciliation，并且 Runner 注册的 adapter、origin 和目标能力匹配时才领取核对。Runner 必须能够使用该目标的 Agent 凭据。实际发现必须与冻结 discovery 一致；目标服务升级、凭据缺失、404/410、身份冲突等均保留 unknown。

统一协议要求按原幂等键查询持久化运行，快照同时包含 task_id、attempt_id、run_id、revision、observed_at 和完整终态。核对只 GET capabilities 和 GET runs/by-key/{原键}，不调用 prepare、资源上传、execute、cancel 或 cleanup，不重发任务，不创建 Attempt 或业务 WorkItem。即使平台未收到远端 run_id，仍可用原键找回操作；已保存 run_id 时必须完全匹配。缺少原执行意图的工作不走此流程，仍使用现有准备阶段恢复规则。

通用 `http` 的 reconcile POST 和 Python 的 reconcile 钩子只保留原有效租约期间的行为：其当前契约没有统一的重启后身份回显、持久化 revision 和全终态停止确认约束，不能仅凭 reconciliation=true 推导可靠重启查询。它们及不具备查询能力的目标仍需人工 resolve。参考 Agent 服务自身重启后可能保守返回 unknown；Eyes 不替该服务推断结果，也不重放它的真实后端。

## 状态、额度与证据

Scheduler 沿用现有扫描：执行意图之后租约失效或停止未确认，Attempt/CaseRun/业务 WorkItem 转 unknown，旧业务 lease token 失效，原全局、项目、目标和实验执行额度继续占用。在线或重启后的匹配 Runner 自动领取这些 unknown 的**独立查询租约**，无需原 Runner 的磁盘目录或存活状态。没有可用匹配 Runner 时保留未知状态，不由 Scheduler 直接持有目标凭据或访问目标。

| 查询事实 | 状态与额度 |
| --- | --- |
| accepted/queued/running/cancel_requested/unknown | 记录快照；unknown 与原额度保留 |
| 连接失败、HTTP 错误、无效协议、能力变化 | 记录 query_failed 或 capability_mismatch；unknown 与原额度保留 |
| task/attempt/run 不匹配、revision 回退或同 revision 内容冲突 | 记录 identity_mismatch/revision_conflict；unknown 与原额度保留 |
| succeeded/failed/cancelled/timed_out，协议校验通过，停止确认且有完成时间 | 原 Attempt/CaseRun 更新为原远端终态；业务 WorkItem completed，释放原额度 |
| 查询租约过期、另一查询已接管或人工已 resolve | 迟到快照作为来源事实保存，late=true；不更新当前状态或额度 |

业务取消/截止时间不会把查询到的真实成功改成取消/超时；采用原操作的可信终态。自动流程不会主动停止远端工作，长时间 running 继续占额，维护者应在目标侧确认停止或结果。

领取、查询响应和应用终态都通过现有不可变 `resolutions` 表追加记录：来源 automatic_agent_http_query、query_id、Runner/凭据身份、领取/接收时间、原远端标识、快照中的 observed_at、revision、结果和诊断。无响应查询的领取记录保留 expires_at；后续重新领取会追加 expired 诊断。`GET /v1/attempts/{id}` 的 resolutions 可读取这些历史。平台不保存解析后的目标凭据，Runner 对快照按目标密钥字面值和已知字段脱敏，错误不保存远端响应正文。

状态应用复用 resolve 领域规则，但来源与 manager_reconciliation 区分。原 result 保存在 previous_result；旧事件、清单、ScoreRun、Score 和报告不重写。新增核对清单为 partial，cleanup 状态仍保留原值，原清理未知不会因远端终态变成成功。核对不补下载远端事件/产物，快照中的远端证据和产物描述仅是查询来源事实，不是已登记的 Eyes 证据。成功后按实际清单及原评分配置创建评分/等待/证据不足记录；后续补充证据须显式 rescore 才纳入新的评分，不覆盖历史。

## 并发、重传和重启

公开接口新增 `POST /v1/reconciliation/claim`（ReconciliationClaim）及 `POST /v1/work/{id}/reconciliation-result`（ReconciliationSubmission），权限均为 runner，受项目、目标及 execute 工作范围限制。查询领取返回 ReconciliationAssignment，包含原任务身份、原键、目标快照和独立 lease token，不携带评分预期或重新执行输入。公共契约可从 `/v1/contracts` 获取。

现有固定顺序 advisory lock、短事务及行锁协调多进程；网络请求在事务之外。查询租约为 180 秒。每个 Runner 同时最多一个自动查询，不消耗新业务执行额度；独立任务不会阻塞业务心跳。每次领取即在 `work_items.reconciliation` 持久化下一可领取时间，失联时按租约期限加退避；正常响应后退避为 15、30、60……最多 3600 秒。次数和截止时间不会因 API、Scheduler 或 Runner 重启清零。

提交使用原查询令牌与完整载荷摘要。同令牌同内容重传返回 duplicate；不同内容返回 409/query_conflict。迟到查询有自己的不可变来源记录但不应用；旧业务 Runner 的结果提交仍由原 lease 校验拒绝，已接受业务结果的重传保持现有去重语义。人工 resolve 和查询应用受同一调度锁协调，先完成的事实决定当前状态。

Runner 在私有 `state_dir/reconciliation/<query-id>/` 原子保存 assignment.json 和 result.json；查询观察使用现有有界 outbox 的 completion 通道提交，ack.json 表示 API 持久化确认。API/网络恢复后补传原载荷；即使租约已过期，也只追加迟到事实。outbox 满时保留 journal，后续扫描继续入队；达到 75% 时暂停新查询。只有 assignment、没有 result 的崩溃查询不在本地重新执行，由数据库查询租约和退避安排再次只读查询。目录保留供排障，沿用部署者的私有数据保留策略。

## 升级与历史数据

升级前暂停领取并结束/核对活动工作，停止服务写入端，备份 PostgreSQL 与证据卷。按原环境运行 `uv run alembic upgrade head`，确认 head 为 `0005_reconciliation`，再启动同源码版本的 API、Scheduler 和 Runner。Runner 的安装包也必须更新，不能仅替换 Supervisor 的 PYTHONPATH。迁移增加一个非空 JSONB 字段，历史工作缺省为 `{}`；不重写 Attempt、结果、评分、证据或核对历史。历史符合能力条件的 unknown 在新 Runner 可用后自动领取；其他历史未知仍保留原额度。

控制协议 1.0 增加新契约/端点，旧业务领取、心跳、结果、人工 resolve 请求形状不变；外部 Agent 协议和 Schema 不变。旧 Runner 不会主动调用新接口，未知工作等待新 Runner 或人工核对。新 Runner 配旧 API 的核对端点不可用，无法自动恢复，部署应先升级控制端。本任务不推进普通契约显式版本迁移。

随后独立任务已落实普通契约的显式 schema_version 要求：最新源码的升级顺序、旧请求窗口及 outbox 读取规则见[版本迁移说明](contract-version-migration.md)。这不改变本页未知结果、查询身份与额度规则，也不补 AgentRun 的 protocol_version。

降级到 0004 会丢弃查询租约/退避字段，必须先停止所有新 Runner 查询与 API/Scheduler 写入，再执行 downgrade；原不可变 resolutions 保留。降级不会撤销已经确认的终态或恢复已释放额度。恢复旧版整体运行数据应使用升级前备份，不能用降级迁移推测远端事实。

## 人工恢复操作

1. 通过 Attempt 详情核对 unknown 原因、原幂等键、remote_operation_id、resolutions 和实际证据；不要创建“恢复执行”实验来绕过额度。
2. 检查目标原操作是否仍运行，Runner 的 origin、凭据引用和 discovery 是否匹配，Scheduler/API readiness 是否正常。修复通信后让查询按数据库退避继续，不修改原键或业务租约。
3. 对能力不足、记录过期、目标自身 unknown 或长期运行的情况，在远端维护界面/日志/业务记录中确认原操作的结果及全部活动已停止；仅本地进程退出、租约过期或查询 404 都不足以解除额度。
4. 只有可信事实齐全时，manage 身份调用 `POST /v1/attempts/{id}/resolve`，提供 status、reason、stopped_confirmed=true，成功需 output。reason 说明来源、原操作身份和停止证据，去除凭据。没有确认时保持 unknown。
5. 检查新 resolutions、Attempt/CaseRun、实验状态和额度变化；保留旧结果、拒绝的迟到上报及证据目录。需要补充证据评分时显式 rescore。

## 本次检查与尚未验证项

实际执行了源码规范、格式检查、字节编译及 PostgreSQL 离线迁移 SQL 生成（0004 → 0005，单个 ADD COLUMN 和 head 更新）。这不是实际 PostgreSQL 迁移或并发故障验收。仓库没有新增/修改测试、用例、fixtures、mocks 或模拟 Agent；没有提交私有运行数据。

2026-10-11 的环境检查：`docker ps --format '{{.Names}}'` 失败，Docker Desktop Linux engine 管道不存在；历史控制 API 127.0.0.1:18046 与 Agent 127.0.0.1:19045 的只读就绪/能力探测均连接失败。未启动/停止已有服务，未修改既有实验或数据。因此本次没有实际 Runner 整体崩溃、网络/API 中断恢复或停止确认验收，不能沿用前次正常终态重启记录作为本次故障证据。

待环境恢复，在独立 PostgreSQL 数据库、证据卷、Agent 状态存储、端口、Runner 状态目录和限定新目标的凭据下，使用现有真实 MewCode 回调、原任务及评分器验证以下项目；不故障注入已有服务，也不使用模拟结果：

- 活动 Runner 整体强制退出 → 租约失效 → unknown/占额 → 匹配 Runner 重启查询原操作；验证只有一个远端 run、一个 Attempt，没有业务重跑。
- Agent 查询网络不可达、控制 API 中断及恢复；保留每阶段原始状态、额度、查询/退避/补传和迟到记录。
- 多 Runner 竞争、重复提交、旧 Runner 迟到结果、查询租约失效、API/Scheduler 服务重启，确认幂等和额度只释放一次。
- 目标仍 running、目标自身 unknown、查询 404/410、能力变化及真实停止确认；未确认分支继续占额，确认终态才释放。
- PostgreSQL 实际升级/重启，核对历史数据、清单、评分和报告不被覆盖，成功恢复但证据缺失时明确 evidence partial/insufficient_evidence。

上述故障项目均为**待验证/当前环境阻塞**，取消/资源正向能力仍需另一个真正支持这些能力的目标；不会因为 MewCode cancellation=false 而伪造停止验收。

2026-10-11 验收审查补充：后续版本迁移任务已在独立 PostgreSQL 实际执行 0001～0005，并在真实历史冷态副本执行 0004→0005；迁移日志和副本前后原执行/清单/评分记录已核对，见[兼容验收](contract-compatibility-validation.md)及[本轮审查](acceptance-review-20261011.md)。因此实际升级不再完全缺证据，但这些操作没有运行活动未知任务的自动核对，不能替代上述故障矩阵。本轮 Docker Linux 引擎管道再次不可达，未启动或中断原服务，任务二结论为部分通过、真实安全恢复仍无法确认。此前环境检查作为历史记录保留。
