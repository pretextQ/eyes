# 实验与批次取消审计

2026-10-14 实现；迁移 `0007_cancellation_audit`，只覆盖实验和批次取消，不是通用审计平台。独立真实材料检查见[验收记录](cancellation-audit-20261014.md)。

## 入口、身份与记录

公开入口为 `POST /v1/experiments/{id}/cancel` 与 `POST /v1/experiment-batches/{id}/cancel`。Web、CLI 调用同一入口；路由均调用 `experiments/cancellation.py`，原调度实现成为内部 `_cancel`，原无审计批次取消函数移除。Runner 的远端取消、执行上报与核对是不同事实，不创建用户取消审计。

两入口要求 manage；审计查询允许 read/manage，Runner 被拒绝。身份只取认证后的 Credential，客户端不能指定 actor/project/time/outcome。`actor_id` 是凭据 UUID，`actor_role` 是当时角色；没有实名用户系统，共享凭据无法确定自然人。凭据撤销或删除不改写历史。

`cancellation_audits` 保存：`id`、`project_id`、`object_kind`（experiment/batch）、`object_id`、`parent_id`、服务端 UTC `created_at`、`actor_id`、`actor_role`、可空 `reason`、`outcome`、`http_status`、`result`。根记录时间来自认证处理进入后的服务端时钟；成员记录时间来自成员处理。审计提交后意味着平台处理事实已持久化；不存在先提交“已请求”再异步修改同一记录的流程。

实验 result 保存处理前后的调度状态、CaseRun/Attempt/WorkItem/ScoreRun/EvidenceWait 状态计数、预留额度数及评分停止请求计数。批次根记录保存各处理结果计数及成员数，每成员追加 experiment 记录，以 parent_id 关联根 ID；成员单独取消的记录没有父请求。没有保存输入、输出、评分正文、请求头或令牌。内部仅保存请求键与规范化参数的摘要，不对查询公开。

## 事务与失败规则

沿用维护共享锁、容量保护（启用时）和既有固定顺序的调度事务锁；实验与批次取消因此与领取、上报、恢复及其他取消串行协调。取消状态与所有审计行在 API 的同一外层事务提交；审计插入、提交或容量检查失败时整个请求回滚，不会留下已生效却无审计的取消。

| outcome | 平台实际结果 |
| --- | --- |
| processed | 处理前后平台状态或计数改变；包括排队取消、停止请求及评分处理，不表示 Agent 已停止 |
| already_finished | 进入时调度已 completed/completed_with_unresolved，原结果保持；unknown 仍可能保留额度 |
| no_change | 非结束对象没有新增平台改变，例如原停止请求仍待确认 |
| failed | 经认证管理请求的领域处理失败；对象不存在或跨项目均为相同 404/not_found，不泄露其他项目事实 |
| partial_failure | 批次中有成员领域失败；各成员以 savepoint 回滚自身失败处理，其他成员及父/子审计一起提交 |

实验领域失败通过返回错误响应而非抛出外层异常提交失败记录。批次成员失败如实记录，父请求为 partial_failure；返回批次详情和审计，不能将 HTTP 200 解读为全部成员已取消。数据库、事务或非预期程序错误回滚整个请求，无可提交审计；调用方按同键重试，运维查看服务日志。未认证、角色拒绝、契约/长度错误及同键参数冲突在处理前拒绝，不追加取消审计：前两者没有授权管理意图，后两者没有新的合法操作。这里不做全站安全拒绝日志。

## 状态边界

审计分别表达用户取消意图与平台本次处理。远端停止确认仍由原 Attempt 的可信结果/核对事实表达，审计不是停止证据。completed 仍是调度结束；用例/Attempt 的 cancelled、cancelled_runs 与取消审计各自展示。未确认的 cancel_requested/unknown 与额度保留规则不变。重评分、恢复、正常完成不会覆盖取消历史，也不反向修改某次请求的结果快照。

## 契约、客户端与重试

旧客户端无 body、无请求键仍可调用，响应保留原实验/批次字段，追加 `cancellation_audit` 与 `duplicate`。新 body 为 `{"schema_version":"1.0","reason":"可选理由"}`；reason 可缺省/null。请求键可选，`Idempotency-Key` 为 1～200 字符，建议随机 UUID；不放密钥。

reason 输入最多 1000 字符，超长 422；空白归一为 null，移除控制和双向控制字符，遮蔽常见 Bearer/eyes_/sk- 令牌形式，遮蔽后的保存值仍最多 1000 字符。Web 用 React 文本转义、换行/长词处理，不解析 HTML/Markdown；弹窗提示勿填密钥。此有限处理不能识别任意自由文本中的秘密，管理者应仅填写必要的操作理由。

同项目、同认证凭据、同请求键、同对象/规范化理由为传输重试，返回原审计 ID、原结果快照和 duplicate=true，不再次取消、不追加父/子行。键是两个入口共用的凭据作用域；同键换对象/理由为 409。响应的对象详情为当前状态，重试后的原处理结果以 cancellation_audit 为准；对象删除后返回 object_deleted=true 及原审计。已保存的失败结果同键重试仍返回原失败，需要新的独立操作时换键。

不同键或无键表示独立操作，即使对象已结束也追加真实 no-op 事实；不能按相同文本/时间自动合并人的两次操作。无键旧客户端没有传输去重保障，禁止无界自动重试。Web 同一未改理由的失败重试保持键，改变理由/成功后的独立操作用新键；CLI `eyes cancel UUID --reason TEXT --key UUID`、`eyes cancel-batch UUID --reason TEXT --key UUID`，传输重试显式复用原键。客户端不自动循环取消。

## 项目查询与 Web

`GET /v1/cancellation-audits?limit=50&offset=0`，limit 1～200，offset 非负；服务端从认证上下文限定项目。可选 object_kind、object_id、parent_id，按服务端时间及 ID 倒序稳定分页。不传 project_id，跨项目对象过滤返回空集合。offset 分页在并发追加时可能发生页面位移，回看第一页即可；不承诺分页全程快照。

实验、批次详情显示对象审计；批次父记录可按需展开分页成员处理；「运行状态」显示项目范围历史。均有加载、空、错误与分页状态。读取凭据可查看项目审计；操作权限由服务端强制管理角色。历史对象不存在仍可从项目查询保留的 ID 和结果。

## 保留、备份与删除

PostgreSQL trigger 拒绝审计 UPDATE/DELETE；应用无修改/删除接口，证据/观测清理不清除审计。仅追加，默认随项目部署长期保留；没有自动过期/裁剪。每次请求的理由和结果规模有界，批次最多 32 成员，同键重传不增长；不同合法独立操作的历史总量随使用增长，需监测数据库/备份容量。这不是审计容量硬配额或无限存储承诺。

对象、项目和凭据 UUID 刻意不使用级联外键，不随原对象删除丢失关联身份；父子关联在同事务由领域服务生成。项目删除后没有可用的原项目认证入口，记录仍在备份/数据库保留，不转交别的项目。当前没有公开实验/项目删除 API；未来删除流程也不得级联审计。具备数据库所有者权限的管理员仍可改 schema/禁用 trigger，首版不是防特权篡改或签名账本。

升级前停写、备份数据库与证据卷，再迁移 head 0007，一起重启控制端/Scheduler。历史取消不能凭当前状态补造操作者/时间/理由，新表从实际新请求开始记录。当前服务 readiness 要求 0007；非空审计表的 downgrade 拒绝，降级需恢复取消审计产生前的备份，不能把历史丢弃当作无损迁移。

`eyes-ops backup` 完整 dump 包含审计和不可变 trigger；同版 restore 恢复所有审计 ID/时间/理由/结果，不重记为新取消。旧 0005/0006 备份允许用当前 restore 恢复到空数据库/独立空证据目录；原完整性与 Runner 撤销/未知占额恢复规则保持，随后必须 `alembic upgrade head` 再启动 API。更旧/未知/未来 revision 拒绝；早期备份也不会被补造取消历史。POSIX 备份同步路径仍在本机 Linux 容器运行，Windows 原生备份支持未完成。
