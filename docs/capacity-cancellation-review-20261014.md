# 容量保护与取消审计独立复核（2026-10-14）

本轮直接审查 `f4f97ba`、`b5b96b9` 的提交与实际源码，并读取 AGENT、README、PLAN、架构、功能契约和既有验收记录。日期为 Asia/Shanghai，起点 `b5b96b9`，工作区干净。结论不以开发总结代替运行证据。

## 结论

| 项目 | 独立结论 | 判定范围 |
| --- | --- | --- |
| 容量保护与告警 | 部分通过 | API/CLI、小额度拒收、并发与幂等、恢复、项目权限及当前告警已有真实证据；没有容量 Web 展示，local/recovery 新增拒收、发布进程强杀及实际磁盘故障等仍缺运行证据 |
| 取消操作审计 | 通过本轮范围 | 实验/批次入口、认证身份、父子结果、并发与请求去重、分页权限、追加持久化、迁移/恢复和 Web 已核实；不代表活动远端停止或基础设施失败矩阵通过 |

未发现本轮范围内必须修复的明确代码 Bug；只同步文档和验收结论。容量 Web、持久告警历史/通知、物理硬配额是明确未实现的能力边界，不能将其写成已通过。未覆盖故障分支属于证据不足，不能据此断言实现失败。当前按需用途没有必须追加的开发任务；真实改善/退化和 24h 继续为未来可选验证。

发现并更正一处既有验收记录计数错误：0007完整备份/恢复审计各11条（processed=5、already_finished=4、failed=2），完整文件摘要一致；原文写10条，实际恢复API只取前10条。保留更正说明，不将分页数量当总数或宣称数据丢失。

## 源码核对

- `src/eyes/server/api/dependencies.py:17` 的函数作用域事务在响应发送前完成容量核对和提交；`operations/capacity.py:23` 获取 PostgreSQL 74003 事务锁，提交前 flush 后重新聚合，仅增长且超限时 507/整笔回滚。普通事件、公共/local 观测、恢复事件共享该依赖；没有持久预留台账。进程失联依赖数据库结束事务释放锁，重启从实际内容重计，不会留下永久逻辑占额。没有实测强杀此分支。
- `operations/capacity.py:10` 计量 Event.content 和 ObservedEvent.content 的 JSONB 文本字节；默认额度/产物余量为 0，warning 为 90，与 Settings、样例及 Compose 一致。过期残留仍计量；prompt、结果、评分、清单、审计、索引/WAL/备份均不计，不是数据库硬容量上限。所有 API 配置必须一致且停写切换，直接 SQL 不受保护。
- `evidence/service.py:125` 先校验原去重/冲突，新增才增长；原生事件另按真实身份去重。`LocalArtifactStore` 的 publish 在同卷永久锁文件上 flock，测量 available bytes 并估算块分配后写入/fsync/发布；ready 同内容重传先校验声明然后复用登记，恢复实际重建仍调用 publish。孤立文件计入真实空间、由原维护回收；锁不约束外部写入，也不是文件系统硬配额。
- `operations/capacity.py:58` 测量失败为 null/unknown；数据库失败返回错误，未冒充 0。`api/routes.py:66` 容量仅 Manager 且从身份取项目。告警是稳定 ID 的当前集合，无追加记录/历史/通知。搜索全部 frontend 源码确认没有容量查询或面板；运维说明已明确保留此边界。
- `api/routes.py:175`、`:281` 两个取消入口均调用 `experiments/cancellation.py:113`；身份来自认证 Credential，角色必须 manage。请求键只存摘要；理由最多 1000 字符，去控制字符并有限遮蔽常见令牌；客户端无法指定 actor/time/outcome。自由文本中任意秘密的识别不保证，契约已明确。
- `experiments/cancellation.py:75` 在成员 savepoint 中处理状态，外层同事务追加审计；失败成员回滚后追加 failed，批次汇总各成员真实 outcome 并关联 parent_id。非预期数据库/提交失败回滚整个请求；同键按项目/凭据和参数摘要返回原事实，独立键追加 no-op。没有单独提前提交取消，未实测 insert/commit 故障注入。
- `scheduling/service.py:505` 保持 completed/completed_with_unresolved、cancel_requested 和 unknown 的原规则；审计 snapshot 是请求的前后平台计数，不是停止确认。批次不将所有成员统一写为 cancelled。`cancellation.py:195` 项目过滤后按时间/ID分页；Reader允许read/manage，Runner拒绝；offset不是并发追加的快照分页。
- `0007_cancellation_audit.py` 的 UPDATE/DELETE trigger、非空降级拒绝与独立 UUID 保留一致；`operations/backup.py:140` 接受0005/0006/当前版本，恢复空目标后需升级。`frontend/src/components/CancellationHistory.tsx` 使用文本转义、分页和按需成员展开；实验/批次/Operations均挂载，原截图与HTTP结果相符。

## 直接读取的原始材料

以下均在忽略的私有 `data/` 内，未输出/提交令牌、请求正文或业务证据。既有材料与本轮复验分开，未把旧故障称为新活动实验。

| 原始材料 | 核实事实 |
| --- | --- |
| `capacity-20261013/observation-concurrent.json` | 同项目额度1876，两来源真实并发一200/一507；拒收增长530，用量1876 |
| `observation-atlimit-repeat.json`、`experiment-overlimit-duplicate.json`、`experiment-span-envelope-rejected.json` | 满额度重传确认不占新额；新增实验正文587在277372额度拒收，与原去重语义一致 |
| `artifact-final-rejected.json`、`artifact-final-recovered.json`、`final-verified-artifact.bin`、`final-audit.log` | 130字节原文件，最低余量2TB时507，降低门槛后ready与下载；拒收响应有8192分配余量，最终audit无问题 |
| `repeated-alert-1/2.json`、`final-recovered-alerts.json`、`unknown-volume-and-recovered-quota.log` | 同alert ID，恢复后空集合；不可测卷三项字节为null/unknown |
| `unchanged-business-rows.json`及修正基线记录 | 原35 WorkItem首次基线比较有2差异；与实际复制源replica-after-pages核对为0，历史失败保留 |
| `cancellation-20261014/batch-members.json`、`batch-repeat.json`、`concurrent-same-1/2.json` | 混合成员分别processed/already_finished，共享父ID；同键并发共享原审计ID、一个duplicate=true |
| `before/after-attempts.json`、`unknown-before/after.json`、`full-audit-source/restored.json` | 本轮独立计算SHA-256，三组各自完全相同：原Attempt、unknown及备份审计完整内容保持 |
| `read/runner/other-*.json`、`reason-limit.json`、`forged-actor.json`、`reason-redacted.json` | 分页/项目/角色拒绝和理由限制，与认证及契约源码相符 |
| `backup-verified.log`、`restore-verified.log`、旧版本恢复日志及`nonempty-downgrade.log` | 0007备份/恢复27 ready、49清单、16评分无问题；旧0005/0006恢复兼容，非空降级拒绝，未补造旧审计 |
| `web-cancel-final.png`、`web-results.json` | 3个排队用例取消，Attempt=0；Web显示认证凭据、理由及平台请求处理，明确提示不能证明Agent停止 |

## 本轮隔离复验

原容器全部保持停止。Docker最初不可用，启动已有Docker Desktop后，以源卷只读挂载复制已停止的 cancellation PG/产物到新 `eyes-independent-20261014-*` 卷/网络；PG18.6，缓存控制镜像Python3.14.7，以当前src只读挂载。仅启动PG/API，未启动Runner/Scheduler/Agent/评分器，不调用模型。复制命令用了本地未标记的`postgres:18`别名，Docker拉取该别名（与已有18.6同摘要），未增加项目依赖。初次无POSTGRES环境变量生成pg.env失败；改为隔离网络、无宿主端口的已有库启动方式后继续，不将失败记作通过。

私有原始输出位于 `data/independent-20261014/`，没有新增验收脚本、测试、fixtures、mocks或断言。具体真实操作：

1. 使用既有 `eyes-admin bootstrap` 建立独立项目，公开API注册名称明确为archival replay的来源。完整复用原 `observation-real-first.json`，不修改事件ID/时间/内容，不生成新Agent事实。
2. `EYES_PROJECT_EVENT_CONTENT_BYTES=1` 时POST返回507、requested_growth=530；SQL核对该项目新增ObservedEvent为0。
3. 停止旧API并以统一额度530启动新API：同原请求200，再次传输200；SQL实际为1条/530字节，容量状态blocked。拒收后未永久占额，恢复配置后可接收，满额度重传不重复增长。
4. 原已结束实验 `12a6667e-bdf1-47fe-8caf-82b488ef4f44` 发起新合法取消请求200/already_finished；审计前后均3 succeeded、3 completed评分及reserved=0。新审计 `22cff48e-2819-44ac-9bdc-3d30875893f5` 在副本真实追加，不更改原现场。
5. 实际 `docker restart` API，同键重传200/duplicate=true并返回原审计ID；分页读原历史。read查询审计200、查询容量403。
6. 副本执行事务性UPDATE原审计，被PostgreSQL `published records are immutable`拒绝；最终SQL为1条观测/530字节、15条审计（复制时14条+新合法请求1条）。

本轮不重新做已具备原始证据的备份/浏览器/并发操作，不新增磁盘耗尽或活动停止事实。所有本轮PG/API容器结束时正常停止，原现场未启动/修改；新私有卷保留。仅文档改动执行diff及链接核对，不称为源码运行/构建检查；未重复无新风险的全量构建。

仍未实测：local/recovery新增拒收、产物多进程竞争/强杀/ENOSPC/EDQUOT/inode/慢盘，取消审计insert/commit基础设施失败、partial_failure活动成员、活动远端停止正向；源码结构检查不能替代这些证据。共享凭据不是实名身份，追加trigger不防数据库所有者，审计总量无硬配额，未知任务额度不因取消释放。这些边界不升级为当前必做开发。
