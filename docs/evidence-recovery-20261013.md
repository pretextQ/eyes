# 原操作证据恢复修复与实际复验

日期：2026-10-13，Asia/Shanghai。源码基线 Eyes `64fb0dba5ecbfe6f836124104e78036500ac471b`，本页修复为其后的独立提交。trae 工作区 `e6e0382` 无修改；实际读取的接入端仍用原冻结 trae `357d2ec`、MewCode `3f10408`，不升级目标版本、不重新执行 Agent。

## 缺口分类与源码修复

旧 `reconciliation` 只核对原幂等键的终态：这是原实现的明确设计边界，不是 GET 返回成功就应该自动证明证据或清理成功。缺失实现是原事件/产物下载、跨 Runner 上传授权和补齐后的清单封存。实际 Bug 风险是外层 Runner 事件 ID 会随采集者变化，单靠外层去重会重复登记同一原生事件；旧 ready 登记也不能证明磁盘字节仍在。

新增 `server/scheduling/recovery.py`、`runner/recovery.py`，复用现有 `work_items.reconciliation` JSONB 保存独立证据租约、退避、原快照、分页回执、游标及产物回执。只选择已由可信自动核对完成、未占额的原工作；历史符合条件的工作也可领取。租约不授予执行权限，不新增业务 Attempt/执行工作，不改变 unknown、取消或执行额度语义。

流程先按原键 GET 能力及 AgentRun，再核对项目/凭据/目标范围、task/attempt/run、冻结 discovery、revision 不回退、原终态及原结果一致。事件页校验 run、游标、稳定原生 ID、内容、sequence 冲突与跨页顺序；保留原生发生时间/来源，并关联原 Attempt trace。普通事件接收也识别同一原生事件，保留既有记录，不改写旧外层封装。一般 producer/event ID 冲突规则保持。

产物仅接受原 AgentResult 声明的 UUID；远端和上传端均校验大小、SHA-256，使用既有受控存储键和登记规则。已有 ready 字节缺失/损坏时只发布校验过的原内容，保留登记身份；此磁盘修复分支本轮仅源码核对。文件要求缺失、pending 上传及不支持 events/artifacts 都保留明确缺口。封存同时要求远端结果和完整分页流均 sealed/零丢弃，不能由执行成功推导。

清理状态只采用已重新认证的原 AgentResult 的明确 succeeded/failed；远端 unknown 不提升原清理状态。本轮两个原结果实际明确报告 succeeded。这不是任意工具子进程或供应商停止的通用证明。

Runner 每工作最多保存一个待确认页/产物，原子写入 `state_dir/evidence-recovery/<work-id>/pending.*`；单页受 event_disk_bytes，产物受大小/数量限制，补传受 outbox_bytes 边界。服务端最多 1000 页、10000 原生事件，远端结果最多 100 产物。服务端游标只在事务持久化后推进。租约过期后重新领取、再次核对同一原结果并重绑定待传证据；不重绑定业务执行。失败退避持久化，坏 assignment 留原字节并隔离；上限、冲突、丢失远端记录等仍保持缺口，不强行 sealed。

新增 `recovery_only = true` 运行模式：仍注册并核对原操作，常规 execute/score 领取槽均为零。默认 false 保持原 Runner 行为。

## 清单、评分、协议与升级

补传和最终封存追加新 Manifest；旧清单、原 result 的 previous_result、旧 ScoreRun 与报告不覆盖。证据恢复本身不创建评分。显式 `POST /v1/attempts/{id}/rescore` 选择最新清单、原冻结评分器，生成新的独立 ScoreRun；`retry` 继续绑定原清单。默认汇总/报告仍选择原最早评分，必须明确选择新 ScoreRun 才纳入新报告。

控制协议 1.0 增加 ReconciliationClaim.evidence_recovery（默认 false）、Assignment.phase/恢复游标（均有默认值）、RecoveryEventSubmission，以及 recovery-observation/events/artifacts/close 四端点。旧业务请求和原终态核对形状仍有效，外部 Agent 协议不变。先升级 API，再升级 Runner；旧 API 不认识新增能力，不能声称已恢复。公开 Schema 由现有导出器生成。未增加依赖、表或迁移，head 仍为 `0005_reconciliation`；实际 PostgreSQL `alembic check` 无新增升级操作。旧 JSONB 缺省为空，历史符合条件的可信自动核对工作可补齐。不要通过清空原 JSONB 或改状态来“迁移”恢复。

## 实际操作与结果

本机 Docker Linux/PostgreSQL 18.6 使用原双 Agent 数据库与卷的隔离副本。原 PostgreSQL 仅短暂启动导出后停止，原 API/Runner/Agent 不启动；副本 Agent 在 internal 网络，没有模型网关或外部网络。控制 API 单独增加可供宿主机读取的网络。运行资料保存在 Git 忽略的 `data/recovery-20261013/`，包括第一轮、final、expired 和最终 release 四份独立副本。没有新模型调用或新费用，没有预算沿用/重置，没有 24h 实验。

复用原 `integrations/deta/coding-smoke.jsonl`（SHA-256 `9e868ae0c53f1e2f88d6114b5c76e591647ecd78ef6b6d3882cbaf8b49771e4b`）及原评分器（`3e72cfd6a721cddd420f9d850cf79366545e886ec59b7377424c01fb0737d826`），本轮只评已保存的 fix-mean 输出，不修改任何输入、输出或评测口径。

| 原操作 | trae | MewCode |
| --- | --- | --- |
| Attempt | `5b9be450-8001-465c-a702-e3cf3b76de3e` | `cda81ac0-15e7-4ef1-b89c-71f6c8426a22` |
| 远端 run | `c8ebe3da-ca78-4579-a406-8e8bab0531e3` | 保持原 Attempt 的 remote_operation_id |
| 既有/恢复后原生事件 | 2 → 41 | 17 → 20 |
| 原生内容逐 ID 核对 | 41/41 一致、无新增重复 | 20/20 一致、无新增重复 |
| 恢复产物 | 1 | 3 |
| 最终证据/清理 | sealed / succeeded | sealed / succeeded |
| final 新清单 | `1b023622-3169-4ff5-bbad-a38e68c23ea2`，v12 | `c3e86f87-8da2-4610-8662-00a4b65715d3`，v7 |
| 显式新 ScoreRun | `a6ead392-2a25-4ba7-b623-da2a0b6a1342` | `e9c6cbef-34dc-49ad-9e76-e36c61665635` |
| 独立原评分器 | completed/pass，4/4 检查 | completed/pass，4/4 检查 |

每轮实际暂停 API，在第二页 pending 落盘时强杀整个 trae 恢复 Runner（137），保留同一状态目录，然后恢复。final 轮同租约续传通过；expired 轮暂停 225 秒，超过 180 秒租约及退避，再启动同 Runner。服务端证据领取 count 从 1 → 2，原游标继续，原 pending 页以新证据租约补传；两原操作仍 sealed，无新业务执行。Runner 日志只含原能力/原键/事件/产物 GET 和控制证据请求，没有 Agent prepare/execute/cancel/cleanup。原 2026-10-12 活动业务 Runner 整体退出 → unknown → 同一原操作终态、只释放一次的材料仍引用原验收，本轮新注入的是证据补传阶段整体退出，不能把它冒充新的活动 Agent 执行故障。

两次原 outcome 提交均 200/duplicate=true；重复 observation、事件页、四份原字节和 close 均成功，close 返回同一清单。重复阶段 Event/Artifact/Manifest/ScoreRun/Attempt/报告逐行不变；WorkItem 仅证据租约 expires_at/due_at 续期，不改变业务状态、reserved 或身份。跨目标凭据提交 close 为 403/work_scope。

final 副本执行 Attempt 17 → 17、业务执行工作 21 → 21，reserved 前后均 0。业务旧 Event 310/310、Artifact 23/23、Manifest 37/37、ScoreRun 14/14 逐行不变。新事件 42、产物 4、清单 12、显式 ScoreRun 2；新增工作仅为这两次独立评分。原两个评分实际为 insufficient_evidence（不是 pass，也没有被覆盖），绑定原清单保持。

副本初始没有报告，不能声称已有 17 份报告在本副本重新验证。另实际发布默认历史报告 `4a2d69a0-c6e2-443c-ae07-c4722b27960e`：candidate 仍选原 `6d8fa78a-d6ce-41f1-93ee-36d79a7fc173`；显式新报告 `87424132-0e36-445b-b61c-c129ab15f266` 才选新 `a6ead392`。旧报告读取前后完全一致；取消的另外两项仍计入分母，报告仍可合理 inconclusive，不宣称真实版本改善。

## 检查、失败与未覆盖项

最终 release 副本使用全部最终源码再次完成同一闭环：额外用另一真实原运行的未修改快照/事件页/产物字节做身份拒绝。错误 run 观察 verified=false；同一错误观察重复后 Resolution 完全不变；另一 run 的事件页 409/identity_mismatch，未声明产物 ID 409/artifact_scope，另一原文件的实际字节 422/artifact_integrity。没有修改输出构造通过。恢复 Runner 在不含 Agent 的实际网络命名空间遇到 ConnectError，持久 retry.count=1、15 秒 due_at；停止后改用正确命名空间和同一状态目录，跨重启等到到期再恢复原操作。随后又一次 API 暂停/Runner 整体强杀/续传通过，原 61 事件/4 产物完整。

release 原评分器两项再次 completed/pass、8/8 检查：ScoreRun `67b09d7d-bc88-46de-9610-9eb71d753054` → Manifest `c3fe6d05-be3f-4eb0-9a9e-11034cdbef43`；`9e779302-72ef-4640-a544-41ceefed0aae` → `d8bb956e-2410-42ce-896c-6ae56814f906`。此前 final 两项仍是那一副本的独立历史，本轮新评分共 4 个，不是 4 次 Agent 执行。release 在补传前发布默认历史报告 `91770faa-0f7a-4475-aa76-18a1831f4e29`，补传、显式评分及重复核对后该完整数据库行保持不变；同样保持原 310 Event/23 Artifact/37 Manifest/14 ScoreRun。这补上 final 副本开始时无报告的运行验证边界。

`ruff check src migrations`、`ruff format --check src migrations`、字节编译、`git diff --check` 通过；真实 PostgreSQL `alembic check` 无漂移。未改前端，未运行无关前端构建。仓库无既有自动化测试入口；没有新增/修改测试、fixtures、mocks、数据集或评分器。

初始 Docker 引擎未启动；恢复后原容器仍停止。首次复制卷没有保留文件 UID/GID，Agent SQLite 无法打开；按原文件所有权修正副本后恢复，没有放宽权限。internal 网络不提供宿主机端口，控制端增加独立网络，Agent 保持 internal；采集改为控制容器内真实 GET。采集脚本修正了表名，并保留 Windows 编码/评分详情字段、报告缺少幂等头、API 重启早期读取等失败保留在操作日志或本页，不计为成功，也未更改业务结果制造通过。

新增 ready 文件修复、缺文件要求/pending 封存限制、损坏 journal/磁盘耗尽、超大流/游标冲突等保护分支主要为源码检查；末轮 API 重启后已用当前源码重复核验四份原产物，其他保护分支未逐项注入。独立原 unknown 占额分支、取消/资源正向、远端清理仍 unknown、终态证据后续改变、跨项目及所有权限组合本轮未新增真实故障矩阵。原 unknown 查询/占额规则和停止确认约束保持，不支持统一查询的目标仍需人工核对；M2 不整体升级。

所有原远端 task/运行快照及 trae 预算账本停止前再比对；本轮命名空间恢复为停止状态，卷、失败现场及历史保留。最终对账见私有 close-verification，不能把静态检查或本页文档核对当成额外实际运行。
