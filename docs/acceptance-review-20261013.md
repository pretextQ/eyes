# 恢复与观测生命周期独立验收（2026-10-13）

Windows PowerShell、本机 Docker Linux/PostgreSQL 18.6；Eyes `9755432`（原操作证据恢复）、`b34cd6f`（观测生命周期），trae 工作区 `e6e0382` 干净。按本轮请求重新阅读约定、提交、源码和原始运行材料，不以两篇开发报告的结论代替核对。审查只涉及这两个任务与当前用途；没有扫描无关模块、修改外部 Agent、安装依赖、启动 Agent/Runner/Scheduler、重新执行业务或评分，没有新付费模型调用、24h 实验或仓库测试/fixtures/mocks。

## 结论与当前范围

| 任务 | 结论 | 直接依据 |
| --- | --- | --- |
| 故障后的完整证据与评分恢复 | **通过当前约定范围** | 有源码实现；原 task/attempt/run/幂等键保持，61 原生事件逐 ID/正文一致、4 产物大小/SHA-256 一致，追加清单/独立原评分器 pass 与引用匹配，历史行保留；真实中断/过期租约材料有效，本轮另补查完成回执幂等和真实页冲突 |
| 被动观测生命周期 | **通过当前约定范围** | 有清理服务和 0006 迁移；默认关闭、明确项目/可信服务端时钟、running/disconnected 保护、有界独立批次、过期身份/审计和权限有实现且与原材料一致；100 正文清理、预览/重复执行/API/Web 材料有效，本轮另恢复清理后 dump 检查身份、权限和重复清理 |

两项通过限定为声明支持的统一 agent_http 恢复及项目范围的保留清理，不等于所有原始 M0～M4 条件通过。未发现两项范围内需要修复的新产品 Bug；本轮只修正文档中的当前任务范围和滞后状态，没有业务代码变更。

用户已决定：同一 Agent 不同版本真实改善/退化**不纳入当前验收范围，未来有真实可比材料时再验证**；没有标为通过，比较功能、既有无变化报告、候选检查和历史失败都保留，不再列为当前必做阻塞。24h/多日同为未来可选。按当前按需、既有真实 Agent 用途，未发现必须追加的开发任务；部署备份、迁移至 0006、按项目显式启用保留期是运维操作。更广的取消/资源、故障组合或容量承诺应在需求改变时另定，不为继续开发制造任务。

## 原操作恢复：源码与原始材料复算

源码位置：`runner/recovery.py`、`runner/reconciliation.py`、`server/scheduling/recovery.py`、`server/evidence/service.py`、相关 API/契约。只 GET 原键/原 run/events/artifacts，不调用 prepare/execute/cancel/cleanup；证据租约与业务执行分离，项目/目标/工作类型授权保持。原 Task、Attempt、run、冻结 discovery、revision 与 result 核对，页游标/原生 ID/sequence 冲突校验，产物声明范围与大小/SHA-256 校验都有可运行代码，不是文档能力。

重新解析 `data/recovery-20261013/{final,release,expired}/` 的真实数据库 JSON、远端 run/event JSON、产物 `.bin`、Runner journal/日志和重复提交响应。本轮私有计算输出位于 `data/acceptance-review-20261013/`，不提交正文、凭据、dump 或日志。

- 三份独立材料均为 Attempt 17→17、execute 工作 21→21、reserved 0→0；原 CaseRun、幂等键、remote_operation_id、trace_id 逐项不变。恢复没有新增业务 Attempt。trae 原生事件 41/41、MewCode 20/20 完整正文一致、无重复 ID；新增封装 Event 为 42，和原有 19 原生事件相合。
- 四份真实原字节长度分别 130、12076、464、140，重新计算 SHA-256 全部匹配远端声明和 Eyes 元数据。release 的全部 49 份清单内容摘要、42 份新增 Event 内容摘要匹配。两个新增 ScoreRun 为 completed/pass，均绑定本 Attempt 的 sealed Manifest、原冻结 scorer_id，evidence_refs 属于该清单；没有把原 insufficient_evidence 改为 pass。
- release 原 310 Event、23 Artifact、37 Manifest、14 ScoreRun、1 ComparisonReport 逐行不变。final 的恢复前快照没有报告，不能冒充已有报告保留证据；它后续的默认/显式报告响应按原记录保留，release 才直接具有恢复前后同一报告全行证据。
- pre/post-repeat 中事件、产物、清单、评分、报告、Attempt、Resolution 行一致；WorkItem 仅 reconciliation 内证据租约时钟续期，不改变业务身份/占额。原终态 Resolution applied=true 各一次。新清单与独立评分是显式动作，默认报告仍保留原最早评分。
- expired 材料中强杀后的 pending 页确实落盘，前后日志时间及 Assignment/WorkItem 证明超过租约后再次领取，trae count=2；原游标续传、41/20 事件及 4 字节文件一致。其他材料同租约续传与持久退避也有原日志；不在本轮重新注入已覆盖的长中断。它们是补传阶段故障，不冒充新的活动业务执行故障。

清理事实实际来自两份已重新认证的原结果 cleanup_status=succeeded；源码遇到 unknown 不提升为 succeeded。不支持 events/artifacts、缺文件/pending、流不 sealed/丢弃、身份冲突等不能强行封存；不支持统一查询或未确认停止的目标仍保留 unknown/占额或明确缺口。trae `357d2ec` 的模型停止/预留处理源码与既有真实 unknown 历史继续保留，不从终态成功推导任意供应商/子进程停止。

## 新副本有针对性的实际补查

原 release PG 和产物卷处于 stopped，以只读源挂载复制到新 `eyes-review-20261013-*` 卷（保留 UID/GID），原服务保持停止。新副本 PostgreSQL 实际升级 0005→0006，并启动本轮只读源码控制 API 18101；没有接入 Agent 网络或启动 Runner。

1. 使用两份已有 score journal 的**原完成请求**各重复提交两次，均 200/duplicate=true。采用另一份未修改真实 ScoreOutput 提交到错误工作，409/completion_conflict。8 张相关业务表完整快照不变，评分/清单/报告/Attempt 和执行额度均未增加或覆盖。这里验证的是评分完成回执幂等；显式 rescore 本来就是新评分动作，不能把它泛称为“所有重评分请求都幂等”。
2. 原已过期证据租约的真实 pending 页提交为 409/stale_recovery。为进入页校验分支，仅在此新副本延长该已完成工作证据租约时钟，保留原 token/Runner 身份及页正文；相同页/游标返回 200/duplicate=true，把该真实页关联到另一个已保存游标返回 409/event_conflict。调整时钟之后、两请求前后的业务表完整快照一致，没有持久化伪造事件。此操作不算新领取/新中断的故障证据。
3. 服务用户运行 audit：27 ready Artifact、49 Manifest、16 ScoreRun，status=ok、problems=[]；通过授权 HTTP 再下载 4 产物，均 200，原大小/SHA-256 再次完全匹配。PostgreSQL alembic check 无模型漂移。

这补查了此前没有直接保存重复 ScoreOutput 完成响应和真实同游标页冲突响应的证据；没有新评分计算或新业务执行。

## 观测生命周期：核对及恢复补查

源码确认默认 days=0，正数策略要求明确项目；run/event/max_batches 默认 20/500/10，上限 100/2000/100。使用 terminal_received_at 和 last_seen_at 两者都早于 cutoff，不用 producer 时间；历史明确终态保守回填。running（包括查询显示 disconnected）不清理，来源撤销或失联不能当作停止。每批独立提交，SKIP LOCKED、锁/语句超时和共享备份锁有实现；API 详情锁 run 与清理串行，过期先隐藏正文，后续批次继续排空，事件不可变触发器只允许清空转换。

重新核对 `data/observation-retention-20261013/` 的预览/执行响应、前后全行摘要、权限响应、过期详情与实际 Web 文本/截图。默认禁用和预览未改数据；1/7/1 小批次实际清 1 run/7 event，后续 2 run/93 event，总计 3 run/100 正文。重复清理 0/0、全行摘要不变；B 的 51 事件与 A 未结束前缀的 2 事件摘要保持。**未结束前缀是原真实事件的归档副本和单独时钟调整，不能称为新活动 Agent 故障验证**。最终 API 空 events/expired，Web 不展示流程/任务正文，不误报完整证据；来源无管理/删除权限。第一次触发器回滚、迁移开发期缺函数和 maintenance 停止 137/修复后 0 的失败继续保留，不改写历史。

本轮把清理后真实 custom dump 恢复到新副本中的空库 eyes_observation_review，单事务 pg_restore；0006、两观测表全行 MD5 与原清理后材料完全一致。新 API 18103：A read/manage 200 且 evidence_status=expired、prompt=null、events=[]，B read 404、来源凭据 read 401。项目 A 再执行 maintain --observations-only --apply 为 0/0；两表全行摘要仍相同，原 3 过期 run/100 `{}`、B 51 正文、A running 2 正文保持。

0006 无过期记录可降级、清理后拒绝降级的原实际材料与当前迁移源码一致；本轮恢复没有去掉过期标识。正文/元数据/备份/客户端副本是不同保留对象：逻辑正文清空不是数据库文件缩小、硬容量上限或擦除所有副本。超限拒收、空间告警、审计/备份独立保留和可信人工停止确认未实现。大积压锁竞争、强杀清理/慢盘/磁盘耗尽及长期趋势没有本轮运行证据，继续作为未来扩展边界。

## 检查、失败与交付边界

源码静态核对与本轮 Ruff check/format 通过；没有改 Python/前端业务代码，不重复无关前端构建或耗时检查。实际检查另包括新 PostgreSQL 迁移/alembic check、服务用户 audit、真实 HTTP 回执/下载及独立空库恢复。Web 仅独立检查上一轮保存的实际页面文本和截图，**未重新运行浏览器验收**。文档链接/diff 核对不算运行验证。

本轮操作失败：首次读取 interrupted-pending 误按字典解包，实际为单元素列表，已完成的评分重放没有改数据；修正读取后继续。首次下载请求漏 `/content` 路径得到 404，保留响应，按现有公开路由修正后四项 200/摘要匹配。这两项是核对工具操作错误，不是 Eyes 产品 Bug；没有通过修改结果制造通过。文档编辑首次补丁上下文不匹配，整份补丁未应用，读取确切标题后重新编辑。

本轮仅更新 README/PLAN、文档导航、两篇开发验收的复核入口、平台当前范围和历史验收入口；外部 trae 不修改、不需要提交。所有新副本 API/PG 正常停止、保留卷/私有证据；原现场和历史失败不删除。提交与推送结果以最终 Git 输出为准。
