# Runner 可靠性修复与验收

日期：2026-10-11（Asia/Shanghai）。范围为审查 #3、#5 的本地恢复缺口及 #6；不重新开发协议、自动核对或版本迁移。审查材料的 P0 定级不作为实现依据；这些入口缺陷按 Runner 交付与评分可靠性问题处理。

## 损坏载荷隔离与恢复身份

- assignment、result、核对 journal 与 outbox 按文件校验 JSON、契约及关联身份。恢复沿用 `read_stored_contract` / `explicit_versions` 的缺版本历史读取策略，只在内存投影，不改原文件或摘要；新领取仍沿用 ClaimedWork。
- 工作目录名称须匹配已校验 UUID；出站 outbox 校验 key/文件名、UUID、固定请求路径、所属 Runner 状态目录及结果与 journal 一致性，防止异常标识进入目录/请求路径。
- 损坏工作使用 `corrupt.json` 原地隔离，保留 assignment/result、capture、workspace；禁止该目录恢复、封存和回收。损坏 outbox 原字节与配对 content 转入 `outbox-corrupt/<随机 UUID>/`，记录原文件名、错误类型与可读取的归属。不会生成正常结果、ack 或停止确认，不调用额度释放。
- 健康文件继续扫描和发送。隔离内容不占发送容量；诊断未知归属时保守阻止 sealed 完成/封存，维护者必须核对原始材料后处理，不能仅删除隔离文件绕过证据缺口。已知归属只阻止对应工作的封存。没有自动删除隔离目录。
- 容量不足使用单独 `OutboxCapacityError`；临时读取/写入错误记录文件与 errno 并保留重试，不归类为等待容量；损坏载荷记录文件与异常类型，避免输出含秘密的载荷/校验异常正文。身份指纹文件损坏仍拒绝使用状态目录：不能在凭据归属不确定时补传。
- Runner status 增加损坏 journal/outbox 计数。相关 Ruff check、format、字节编译和 diff 空白检查通过；真实隔离副本故障验证在下文另记，不以静态检查替代。
- 复核核对 result 的 envelope 路径字段时，非字符串等结构损坏同样按文件隔离，不能从契约选择器逃逸成整个恢复循环异常。

## 验收边界

复查 `data/safety-acceptance-20261011/` 已有真实记录，逐项核对后补齐缺口；私有材料、凭据、日志和运行数据不提交。本轮不开展版本回归或备份恢复，不新增/修改仓库测试、用例、fixtures 或 mocks。

## 评分基础设施错误

- 评分输入和固定清单中的产物读取，对 408/425/429/5xx、传输错误和超时最多读取四次，间隔 0.5/1/2 秒；每次请求与退避都受原截止时间、当前有效租约、取消及 Runner 退出信号限制。身份/清单不匹配不重试；不重新领取业务、不重新执行 Agent、不调用 rescore、不自动改历史汇总。
- 认证、租约、最终 API/传输故障与本地读写/完整性失败记录 `error`。仅固定证据视图明确 unavailable/expired，或平台明确返回 410 evidence_expired/artifact_unavailable 时记录 `insufficient_evidence`；评分器自身的明确证据不足结果继续保留。
- 产物下载保留真实 API 错误码，不能将所有 HTTP 失败统一包装成 artifact_unavailable；冻结清单中的产物标识在写目录/请求前进行 UUID 解析。
- 相关 Ruff check/format、字节编译与 diff 空白检查通过；未用模拟 API、评分或 Agent 输出替代真实运行。

## 真实材料与独立环境

源码提交 `363b2ab`、`28648ea`、`2f73dd2`；Windows 宿主机、本机 Docker Linux、Python 3.14、PostgreSQL 15.17，数据库 head `0005_reconciliation`。复用独立安全验收数据库 55443/API 18056；本轮故障仅作用于该独立控制环境和 `data/runner-reliability-20261011/` 新状态副本。已有 `eyes-mewcode-rerun-api` / `eyes-mewcode-rerun-agent` 未被故障注入，原 Agent 状态和原 Runner 持久化材料只读或先复制后注入。

既有真实 Agent 故障记录在 `data/safety-acceptance-20261011/`。本轮恢复独立控制服务，只读核对 PostgreSQL、Agent protocol.sqlite3 与原始请求/状态记录；没有重新执行 Agent，没有修改外部 Agent 核心。新的评分验证通过显式 rescore 创建四个独立 ScoreRun，执行既有冻结评分器，全部绑定原清单 `f8251a3a-0652-40cf-b9ba-2b01ec44273c`。

私有证据在 `data/runner-reliability-20261011/`：`audit.json`、各 Runner 日志、真实领取载荷、前后文件摘要、隔离原字节、实际评分 journal、报告及 readiness 前后清单。全部 Git 忽略；公开文档不包含凭据、日志正文或运行数据。

## 新修复的实际运行

| 场景 | 实际结果 |
| --- | --- |
| assignment 截断、非法 UUID；score result 截断、缺 result；已确认 execution result 截断 | 五个目录均生成定位诊断并保留原载荷/capture；Runner 正常退出 0。健康原评分补传返回 200/写 ack。四个首轮损坏目录的原文件与注入后基线摘要一致；没有回收、封存或生成替代完成结果 |
| 核对 result 的 path 改成数组 | 单目录 AttributeError 被隔离；另一份真实核对原载荷补传返回 200，Runner 退出 0 |
| 真实 outbox JSON 截断，配对真实产物内容不变 | JSON/content 一并保留在 outbox-corrupt；同轮另一份真实产物 POST 201、PUT 200。隔离内容不占发送容量，健康项继续发送 |
| 原权限导致三个副本 assignment 读取 errno 13 | 逐文件记录 journal_read_disk_error / journal_reap_disk_error，Runner 继续注册/发送并退出 0；不记为等待容量。改用独立容器 root 后才完成对应损坏校验；首次权限失败记录保留 |
| API 停止后恢复，真实评分输入读取 | 三次传输重试后第四次成功；读取同一清单及原产物，真实冻结评分器 completed/pass，4/4 功能检查；没有 Agent 执行 |
| PostgreSQL 停止，API 实际返回 503 database_unavailable | 四次读取后停止重试，本地结果 error；提交也遇到 503，原 journal/outbox 保留。恢复后租约已过期，Scheduler 最终记录 error，没有将失败归类为证据不足 |
| 使用另一实际 Runner 凭据处理原领取 | heartbeat 403 触发停止，结果 error；提交 403 拒绝，无越权确认或评分器执行 |
| API 暂停，客户端超时 60 秒、实际租约 10 秒 | 评分读取在租约边界中止，结果 error；API 恢复后旧提交/心跳 409。Scheduler 记录 error，没有等满 60 秒再启动评分器 |

四个新 ScoreRun 的数据库终态分别为 completed、error、error、error，manifest_id 均等于原领取值。原三个基线 ScoreRun 的 status/result/manifest_id 与既有原记录逐项相同。只读复核及新默认报告也确认原最早评分选择不变。

## 安全恢复必需场景

以下为**核实既有真实故障证据及当前持久化状态**，没有重复强杀 Agent/Runner。调度、只读查询和额度机制本轮未重设计；新的坏核对 journal / 健康补传另在上表运行。

| 必需场景 | 核实结果与原始入口 |
| --- | --- |
| 整体 Runner 退出、原操作查询 | whole-positive-kill/history/detail：Attempt `8b11356a-db43-47fb-ae34-1716bc0dca3f` 从 running/claimed/reserved → unknown/reserved → succeeded/completed/unreserved。PostgreSQL 该 CaseRun 只有一个 Attempt，真实 Agent 原键只有一个 run `11fd47af-fd67-4bef-b053-56a94a8b2d67`，结果包含真实停止确认 |
| 竞争、查询租约接管与重复核对 | competition-claims：两个 Runner 同时领取只有一个获得 query。confirmed-before-query-expiry/after-restart 的 token/count/due_at 保持；租约到期追加 expired 诊断，另一查询接管。late-query-repeated-responses 返回 200，再次 duplicate=true |
| 迟到与可信终态只释放一次 | confirmed-final-detail/work：Attempt `40fd0f62-b5e9-4c35-a6a4-dacf2a05477a` 只有一个 Attempt/远端 run；applied=true 的观察只有一次，迟到观察 late=true/applied=false。旧 Runner 恢复后的结果被拒绝；当前 reserved=false，原 terminal snapshot 与 Agent 持久化结果一致 |
| 失败退避跨重启、unknown 占额 | query-failed-work/after-control-restart-work：原未知工作 `92a3adfc-c64d-4124-b4de-3389fe62db20` 的查询次数/下一时间保留。当前仍 unknown/reserved=true，原 CaseRun 只有一个 Attempt，未确认分支 applied=0；后续同项目工作没有绕过原限额执行 |

这关闭本轮指定的安全恢复必需门槛。仍不等于整个 M2 的所有目标/取消/资源能力或故障组合全部验收。

## BUG-001～004

- BUG-001：既有真实磁盘失败轮次 `bug-upload-disk-failure.json` 一项发送成功、另一项保留并退避；`bug-upload-restored.json` 恢复后发送剩余项，pending=0。当前源码的坏 outbox/健康产物并行发送也通过，未重复原故障。
- BUG-002：真实写入中断后孤立内容隔离，原内容摘要一致；正常 JSON/content 配对前后摘要相同。见 bug-orphan-recovery / bug-normal-pair-preserved，沿用有效证据。
- BUG-003：既有真实只读证据卷返回 503 artifact_store_unavailable，探测后目录为空；可写卷返回 200。本轮实际 ready=200，完整文件清单/摘要前后无变化，未登记探测业务产物。
- BUG-004：复核既有浏览器报告截图与持久化请求，报告 `d793eb34-ae8b-495a-a489-3d354ab29ae1` 显式选择新 ScoreRun `f341cdfc-4c2f-4a2c-81be-2b998947f3ca`，integer-cli 行绑定该 completed 记录。新建留空默认报告仍选择原 `2ade72f6-0e80-4134-85f1-5eb76101c391`。旧报告 content/digest/request_digest/id 全部不变；API 响应 created_at 仅时区表示不同，不能据此判历史被改写。

四项行为条件通过；不是同目标版本改善/退化验收，报告仍可合理显示 inconclusive。

## 剩余边界与收尾

本轮指定必需项无环境阻塞。没有将所有磁盘故障码、截止早于租约的独立评分故障、全部 HTTP 状态或缺版本历史组合逐一注入；相应边界有源码检查，不能推广为穷尽故障验证。缺版本历史普通读取继续沿用既有策略，本轮没有伪造历史或开展版本兼容回归。

验收结束后，独立 eyes-safety-api 与 PostgreSQL 55443 恢复为本轮开始时的停止状态；新增容器已退出，原字节、失败日志和运行目录保留。已有 MewCode 重验 API/Agent 继续保持原状态。

统一 HTTP 取消/资源正向能力、第二个统一实现、完整 M2 故障矩阵、同版本真实改善/退化和完整备份恢复仍保留原计划，不属于本轮通过声明。本轮未修改仓库测试、用例、fixtures/mocks、依赖、数据库迁移或外部 Agent 核心；私有失败记录保留。
