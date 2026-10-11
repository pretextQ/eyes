# 完整证据备份恢复与发布风险核查

日期：2026-10-11（Asia/Shanghai），源码基线 `a835823`，当前分支 `main`。先核对 AGENT.md、PLAN、平台说明、迁移及前两轮验收，再复核外部审查报告 #7/#8/#10/#11。本轮没有重新开发统一协议、安全自动核对、版本迁移或已验收的 Runner/Web 修复。

## 前置结果与隔离方式

[Runner 可靠性轮次](runner-reliability-20261011.md)已完成 #3/#5/#6 修复、指定安全恢复必需门槛和 BUG-001～004；[部署/回归轮次](deployment-regression-20261011.md)已完成 #1/#4 定向验收、取消显示核对和真实两版本无变化报告。真实改善/退化、完整故障矩阵和干净部署仍缺证据，沿用原结论，不重跑外部 Agent。

启动本机 Docker Desktop Linux 引擎后，确认既有验收容器停止、原 PostgreSQL 数据目录无 postmaster.pid。用 PowerShell Copy-Item 复制 `data/safety-acceptance-20261011/postgres` 和 `artifacts`，仅在新目录 `data/backup-acceptance-20261011/` 启动数据库副本，端口 55444。原数据库与证据卷没有写入；原材料在运维容器只读挂载。没有启动原 API、Scheduler、Runner 或 Agent。

环境：Windows / PowerShell，Docker Linux 缓存运行镜像 `eyes-mewcode:local`（`sha256:420dba75f4b41b95976e91e0d590cfc9d1fb3397a8a64b39c1c21ed167ceca2a`），Linux Python 3.14.7，数据库 PostgreSQL 15.17。仅在隔离运维容器安装所需 PostgreSQL 客户端，正式 dump/restore 显式使用 `/usr/lib/postgresql/15/bin` 的 15.18；没有修改仓库依赖。它不是干净锁文件镜像部署验收。

宿主机 `python -m alembic heads`、副本 SQL `SELECT version_num FROM alembic_version` 和恢复后容器 `alembic current` 均核实实际 head 为 `0005_reconciliation`，与服务 `SCHEMA_REVISION` 一致；不是依据旧文档指定恢复版本。

## 当前工具的实际备份恢复

直接运行当前 `eyes-ops audit / backup / restore`，使用 `/runtime/src` 的当前源码。数据库地址指向副本；backup 使用导出快照和原生 pg_dump，restore 使用单事务 pg_restore。每次恢复都先创建新空数据库，文件目标不存在；没有覆盖原库、源副本或已有恢复目标。

私有命令结果、逐表内容、摘要、完整备份、HTTP 响应和失败材料均保存在上述 Git 忽略目录。本轮使用的代表性命令（容器内，环境文件中的数据库地址和秘密不公开）：

```sh
set -a; . /validation/source.env; set +a
eyes-ops audit
eyes-ops backup /validation/backup-release --pg-bin-dir /usr/lib/postgresql/15/bin
set -a; . /validation/restore-release.env; set +a
eyes-ops restore /validation/backup-release --pg-bin-dir /usr/lib/postgresql/15/bin
eyes-ops audit
alembic current
```

第一次恢复 `eyes_restore` 包含完整真实业务材料，audit 通过。原库没有 read 凭据，随后在**隔离源副本**通过既有 `admin.issue` 实际签发只读凭据：先为原 unknown 项目签发，后为已有正式版本报告项目签发；没有伪造业务记录。第二次恢复 `eyes_restore_read` 与最终恢复 `eyes_restore_release` 各使用新完整备份和空目录。最终源库 22 个凭据中 13 runner、7 manage、2 read；原业务数量没有变化。

| 对象 | 源副本 → 最终恢复 | 核对结果 |
| --- | --- | --- |
| Project / Target / TargetVersion | 7 / 7 / 7 | ID、归属、全部行内容摘要相同 |
| Experiment / CaseRun / Attempt | 13 / 39 / 20 | 全行规范 JSON 的排序集合 SHA-256 相同；没有新增执行或重排 |
| Event / ready Artifact | 341 / 47 | 事件全行摘要相同；47 个存储键、元数据和原卷/源副本/备份/恢复字节一致 |
| EvidenceManifest / ScoreRun | 86 / 25 | ID、清单内容及摘要、评分结果和固定 manifest_id 均相同；audit 引用检查通过 |
| 固定 ComparisonReport | 17 | ID、请求摘要、内容和摘要全部相同；87 个已选评分侧的 Attempt/ScoreRun/Manifest、清单摘要及证据引用有效 |
| WorkItem / Resolution / EvidenceWait | 62 / 27 / 2 | 全行摘要相同；2 个 unknown 工作及原 reconciliation 字段、reserved=true 均保留 |
| Credential / Runner | 22 / 13 | 13 个 Runner 凭据仅 revoked 改为 true；manage/read 全字段保持，Runner 记录不改写 |

按 PostgreSQL `row_to_json` 提取全部 23 张 public 表，将完整行按键规范化、排序后求 SHA-256，不只比较数量或现有 digest 字段。除 credentials 的预期撤销外，其余 22 张表集合摘要全部相同，空 observation 表也如实记为零。所有产物同时核对 size 与 SHA-256 元数据，并逐字节比较原卷和最终恢复文件。

仍 unknown/reserved 的工作是 `03010abd-de63-4c94-a32d-47214b381baa` 和 `92a3adfc-c64d-4124-b4de-3389fe62db20`。恢复没有确认远端停止、解除额度或产生替代执行。源库没有 claimed 工作，restore recovery 的 safe_requeued/unknown/score_errors/stop_requested 本次均为 0；活动租约恢复分支不在本次材料覆盖内，不能把 0 解读为不存在原 unknown。

源 audit、恢复内置 audit、最终 **API 用户 UID 10001** audit 都返回 ok：47 ready、86 manifests、25 scores、problems=[]。恢复后 API 读取正式报告 `8127257e-0a5d-41f9-87a5-acd0fddb019b`，read/manage 均 HTTP 200、相同 ID 和摘要；抽取一个真实产物经 read 下载 HTTP 200，145 字节及 SHA-256 与原文件一致。跨项目报告 HTTP 404；read 发起取消 HTTP 403；原真实 Runner 凭据下载 HTTP 401。其余产物字节由全量文件核对与服务用户 audit 验证，未声称全量逐 HTTP 下载。

再次对非空最终目标执行 restore，实际退出 3、`restore artifact directory must be empty`，原恢复数据没有变化。报告诊断事务回滚、权限请求及拒绝覆盖后再次提取全表，仍与恢复完成时相同。最后 audit 继续通过。

**结论：当前版本已有完整真实业务材料的备份恢复通过，包含 ready 产物，且服务用户权限修正后可读。** 该结果关闭本轮完整证据恢复任务，不等于 M4、干净 Compose 或全部权限/故障组合通过。

## 实际失败与最小处理

1. 初次私有 shell 环境文件写成 CRLF，容器加载后数据库名带 CR，连接失败；失败目录没有完成 manifest。改为 LF、新备份目录后成功。环境错误及最初输出保留，不归为产品缺陷。
2. 宿主机采集器默认 GBK 写含真实 Unicode 的行数据失败；改用 UTF-8 后完成全量提取。首次记录保留。第一次权限采集选错无报告的 unknown 项目发生 StopIteration；保留后改用真实版本项目。它们不是恢复成功或产品失败的证据。
3. **确认恢复交接的权限缺口**：root 运维进程创建恢复目录为 root/0700、文件 root/0600；root audit 通过，UID 10001 API 实际下载 410、ready 503，目录遍历 permission denied。工具没有部署 UID 参数，也不应自动猜测服务身份。仅对最终恢复目录和直接产物文件执行 chown 10001:10001，保持私有权限及字节；随后服务用户 audit、ready=200 和下载=200 均通过。修正前的 `verification-before-ownership.json`、摘要和日志保留。

第 3 项是执行身份与服务交接文档缺口，未发现需要修改恢复工具的数据逻辑。最小修复是在[平台恢复说明](platform.md#恢复)明确同一服务身份执行或在 root 恢复后交接所有权，并要求以 API 用户 audit、readiness、实际下载复核，不能只凭 root audit 宣称可读。Compose 的手动恢复原本已有 chown 步骤，保留该能力。

## 审查性能项的实际证据和边界

没有新增索引迁移、改变轮询、移除锁或重构 Runner，没有容量压测。实际查询测量仅使用当前小规模真实数据（62 WorkItem、20 Attempt、25 ScoreRun、341 Event）；先在独立恢复库 ANALYZE，保留 `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`。

### #7：索引与具体查询

实际 `pg_indexes/pg_index/pg_constraint` 共 **69 个索引：23 个主键、17 个其他唯一索引、29 个非唯一索引**，包括 0003 循环生成的 observation 索引。原审查按显式名字计 14 个并不能代表真实覆盖。dataset/case/target versions、case_runs.experiment_id、runners.credential_id、清单 attempt/version 等已有普通或唯一索引。

19 个外键首列没有索引覆盖：artifacts.project_id、attempts.runner_id、case_runs.case_version_id、comparison_reports.baseline_id/candidate_id、evidence_waits.scorer_id、experiments.dataset_id/target_id/target_scope_id、resolutions.credential_id、score_runs.manifest_id/scorer_id、work_items.attempt_id/case_run_id/experiment_id/runner_id/score_run_id/target_id/target_scope_id。这是结构清单，不是 19 个已证实慢查询。work_items.project_id 已由 ix_work_queue 首列覆盖；目标/实验保留数受 ix_work_reservations 的 kind/reserved 前缀及后续列支持，不能只看单列外键。

| 实际查询 | 计划和单次执行时间 | 判断 |
| --- | --- | --- |
| refresh_experiment 按 experiment_id 读取 WorkItem status | Seq Scan，6 行，0.014 ms | work_items.experiment_id 是具体候选；当前 62 行顺扫合理，没有慢查询证据 |
| global/project 执行保留数 | 小表 Seq Scan，0.029 / 0.018 ms | 现有 reservations 索引存在，不能据顺扫认定缺索引 |
| 完整执行候选 SQL，含真实 Runner 插件/目标范围、两项关联额度、JSON 并发和 SKIP LOCKED | 1.970 ms；2 个队列候选被额度条件过滤，返回 0；关联子查询部分没有执行 | 按 claim 源码的候选 SQL 核对，不领取或执行业务；没有可领取项场景，不能推广全路径性能 |
| comparison.capture 的 ScoreRun→Attempt→CaseRun 选择 | ix_score_runs_attempt_id Index Scan，其他小表顺扫，0.045 ms | 实际热评分关联已有索引，不按外键总数补齐 |
| Attempt 事件读取与排序 | ix_events_attempt_id Bitmap Index Scan，0.050 ms | 当前没有索引阻塞证据 |

以上六项基础查询另保存队列简化筛选计划（0.030 ms），它不代表完整 claim。完整 claim 单独保留实际参数/计划。后续 P2 先在自然增长的真实库查看调用频率、行数、缓冲读和慢查询；重点复查 experiment_id 的状态刷新/取消/汇总，再评估单列或含排序的组合索引及写入代价。没有依据批量生成“补外键”迁移。

### #8：轮询的生命周期

源码确认 Observation 列表及详情 2 秒，source 列表 10 秒；实验、用例/事件/清单详情常为 10 秒，批次列表 10 秒、详情 5 秒。Observation 详情每轮会按用户已展开 limit 分页重取事件，是真实请求放大的结构依据；本轮恢复库 observation 表为空，没有测得该页实际网络/数据库开销。

列表必须持续发现其他客户端的新任务，不能因本页记录全终态而停止。执行终态仍可补迟到事件、形成新 Manifest、结束 EvidenceWait、retry/rescore 追加评分；批次/实验详情也需反映这些事实。固定报告详情已有按 ID 查询，没有 refetchInterval，适合作为稳定快照。

后续 P2 按列表发现、活动详情、迟到证据/评分可变详情和稳定快照分别设计退避及主动刷新/失效；需要先定义稳定条件或修订标识。不能把 completed/unknown 一律当成停止轮询条件。本轮确认固定轮询存在，未确认其已造成容量或响应故障。

### #10：全局锁及报告事务

当前 scheduling_lock 仍固定顺序 74001→74002，comparison.create 的报告选择、汇总、构建及写入在该锁内；这是保留固定快照一致性的现有机制。在独立恢复库对已有正式三行报告的真实请求调用当前 create，使用诊断请求键，flush 后**回滚整笔事务**，不发布新报告。生成 content/digest 与既有报告完全相同，后续全表摘要确认历史不变。

单次实测维护锁 SQL 0.440 ms、74001 0.246 ms、74002 0.162 ms；这些包含客户端/网络耗时，不是纯等待时间。锁后报告路径 53.464 ms；连接、事务开始到回滚总计 85.658 ms。采集 pg_stat_activity 没有 advisory Lock 等待者，只有本次活动连接及 API 空闲连接。没有并发竞争、租约误过期或 unknown 增长证据；这个样本不能证明高负载下不会等待。

后续 P3 先记录实际事务与锁等待分布，区分读库、Python 汇总、证据封存和提交耗时。出现争用后再评估锁内固定 ID/摘要选择与后续一致快照读取，或保证相同不变量的锁范围调整；评估需覆盖 rescore/取消/过期并发，不能直接移除全局锁。

### #11：运行循环的磁盘调用

`RunnerService.run` 初始化及每轮都直接调用 recover/reap；每轮 outbox.flush 的 async 路径同步 glob/load、读取产物、持久化 ack/rejection、unlink，容量判断 size 使用 rglob/stat。run_work 直接写 assignment/payload/result/intent，atomic_write 同步 fsync 文件和目录；评分产物读取后也在此路径写文件。这些确实位于运行中的事件循环；worker 子进程和 SDK 内部线程的写入不混算。

main.py 的 status 分支是独立 CLI，不能作为阻塞正在运行 Runner 的依据。reconciliation 的网络查询已有 to_thread，但 assignment/result 写入和恢复扫描仍同步。已确认结构上的同步 I/O，**没有本轮慢盘/循环延迟/心跳错过的因果实测**，沿用 P3 风险而非已发生故障。

后续先在真实自然负载记录各磁盘阶段、事件循环延迟及心跳余量，必要时把完整的有序持久化操作移到有界线程执行；保留 write/fsync/rename 顺序、身份检查、outbox lane 锁与异常隔离，不并发改写同一 journal，不用取消线程调用冒充停止落盘。

## 发布仍缺的验收

- 干净环境按锁文件构建并完成完整 Compose 启动/升级及外部开发者独立接入；本轮是缓存运行环境的副本恢复，不能替代干净部署。
- 权限：本轮 read/manage/旧 runner 和跨项目报告边界通过；目标/工作类型范围、另一 Runner 的全部接口、所有下载/管理/观测/过期组合及部署文件 ACL 仍需完整矩阵。
- 证据运维：等待截止、迟到、过期/回收、pending、磁盘耗尽、采集丢弃及中途失败恢复尚未全面验收。源库没有 claimed 工作、pending/expired 产物或 observation 数据，这些不在本轮完整材料覆盖内。
- 容量和长期运行：没有吞吐/并发/大报告/大 outbox/慢盘/多日稳定性实测；上述小样本不能发布容量承诺。仍需环境、版本、负载和测量方法，继续跟进既有依赖审计事项。
- 真实版本改善/退化及完整 M2 目标/取消/资源/故障矩阵沿用原缺口。
- 仓库没有已纳入 Git 的自动化行为测试，CI 静态及迁移检查不能代替它；范围及新增套件需明确授权。本轮没有创建或修改仓库测试、用例、fixtures、mocks，也没有用模拟业务数据替代证据。

收尾：新增 API/运维容器及数据库副本停止，原容器/原数据保持原状态；保留所有新副本、完整备份、首次失败及诊断记录。公开提交仅验收和运维文档，不提交数据、脚本、备份、日志或秘密。M4 仍为部分验收。
