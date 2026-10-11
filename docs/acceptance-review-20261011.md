# 前三个开发任务验收审查

日期：2026-10-11（Asia/Shanghai）。审查基线 `0a6b74d`，最后产品代码提交 `3aa7e50`，迁移 head `0005_reconciliation`。本轮只读审查源码、提交和既有实际记录，仅校准文档；没有修改业务代码、API、迁移、测试、用例或运行数据，没有执行下文的后续任务。

后续进展：Runner 可靠性轮次已修复坏载荷隔离/恢复身份与评分错误分类，完成指定安全恢复必需门槛及 BUG-001～004 行为核实，见 [修复及实际验收](runner-reliability-20261011.md)。本页结论保留为上述基线的历史审查；统一协议/显式版本的其他边界仍按原计划，不升级 M0～M4 为全面通过。

## 结论

| 任务 | 验收结论 | 代码已实现 | 静态检查 | 真实运行已验证 | 待验证 / 阻塞 |
| --- | --- | --- | --- | --- | --- |
| 1. 统一运行时、参考 HTTP 服务与真实 Agent | **部分通过**；基本闭环通过 | Runner 使用 agent_http；发现、幂等提交、按键查询、状态/结果、按能力传输事件/产物、取消/资源路径存在 | 6473c96 的 Ruff/格式/编译检查、3aa7e50 的全量静态记录适用 | 真实 MewCode HTTP 3/3 执行及独立评分；事件/产物对应、认证、重放/冲突、已完成 Agent 服务重启 | 支持取消/资源的真实目标正向流程、活动故障/响应丢失、旧通用 HTTP 实际兼容、第二个统一实现未覆盖 |
| 2. 重启/租约失效后的安全自动核对 | **部分通过**；运行安全验收无法确认 | 只读原键查询、独立租约、原身份及 revision 校验、不可变来源、持久化退避、unknown 占额、可信终态释放 | abd7e7c/3aa7e50 的 Ruff/编译记录；0005 离线 SQL 检查 | 后续独立 PostgreSQL 运行 0001～0005、历史副本 0004→0005 升级；不等于核对运行验证 | Runner 整体崩溃、竞争、查询失败、迟到、退避/重启与只释放一次均没有真实故障记录；本轮 Docker 不可达 |
| 3. 显式版本与兼容迁移 | **部分通过**；已验证范围通过 | 普通 schema_version 严格、有限窗口、生产端同步、文件副本迁移、历史/outbox 内存投影；protocol_version 独立 | 3aa7e50 的后端 Ruff/编译、Web lint/format/build 记录适用 | 严格/窗口 API 与 JSONL、旧请求同键重放；6 份旧完成载荷真实 duplicate 确认；两组旧 SDK/冻结评分器各 3/3、12/12 | 真正缺版本的旧持久化材料、更早 evidence_wait_seconds 缺省快照、首次提交响应丢失、外部 exporter/其他旧客户端、当前 Web 请求运行验收未覆盖 |

“部分通过”表示有已核实的实现和运行子集，尚不足以覆盖题定验收重点；不是已确认某个安全分支错误。未发现可凭本轮源码审查直接定性的新增 P1 代码缺陷，但没有运行证据的分支不能据此判为安全验收通过。

## 审查方法与证据层级

已阅读 AGENT.md、README、PLAN、architecture，以及协议、接入、HTTP 运行时/验证、unknown-recovery、contract-version-migration/compatibility、MewCode 验证与四项 Bug 计划。按提交涉及文件和调用链阅读，没有扫描无关项目、数据库目录或凭据正文。

本轮直接检查 Git 的提交内容与当前源码，并对私有原始 API 记录做必要字段的只读统计/比较，不只引用文档“完成”表述：

- `data/mewcode-http/case-runs.json`：三个原 Attempt 全部 succeeded，三个独立 ScoreRun 全部 completed/pass；`final-facts.json` 的评分清单/引用/独立 trace 关联及 `restart-comparison.json` 对应终态查询记录存在。`protocol-requests.json` 的 31 条原始响应记录同时核对：合法发现/按键/状态/结果/重放 200，冲突 409，未支持取消 422，缺失/错误凭据 401，管理/目标范围拒绝 403。实验为 `e93b6f02-0d9e-4a0d-abba-47e48e305847`，详见[实际 HTTP 记录](agent-http-validation.md)。本轮没有重跑 Agent，也没有重新下载全部产物。
- `data/contract-version-migration/api-records.json`：严格缺版本及缺版本 JSONL 为 422，窗口发布/导入为 201；旧实验请求与显式重放返回相同 ID 和 request_digest。`migration.log` 有 0001～0005 实际升级日志。
- `data/runner-compat-validation-20261011/retransmission-responses.json`：原始记录为 27 次传输异常、6 个 duplicate=true/status=completed 的真实确认。baseline/final case-runs 直接比较得到原 Attempt 集合、执行结果、Manifest、全部原 ScoreRun 相同，仅追加 6 个 ScoreRun；与 summary 的两组 3/3、12/12 相符。`api.log` 有副本 0004→0005 实际迁移记录。详见[兼容验收](contract-compatibility-validation.md)。
- 原始请求、日志、数据库、模型/平台凭据和产物均不提交；公开文档只保留身份、计数、结论和复查入口。上述目录需要本机授权访问，Git 文档本身不能替代私有原始材料。

静态检查采用此前同产品源码的实际命令记录：`ruff check/format --check src migrations integrations`、`compileall`，以及 Web `npm run lint/format:check/build`。从 3aa7e50 到本轮基线只有文档提交，故没有重复执行仍适用的全量检查。`git ls-files '*test*' '*spec*'` 再次没有已跟踪套件，未新建测试或内联断言。

本轮实际 `docker ps --format '{{.Names}} {{.Status}}'` 失败：`dockerDesktopLinuxEngine` 管道不存在。本轮未启动/停止原服务、修复 Desktop 或注入故障，也未把历史 Docker 恢复成功描述为当前可用。历史记录保留，不用本次环境失败撤销此前的运行事实。

## 任务一：协议运行时和真实 HTTP 闭环

提交：实现 `6473c96`，真实验收文档 `18381e4`；后续内部版本构造同步 `3aa7e50`。

代码依据（路径相对仓库根目录，行号为本轮基线）：

- `src/eyes/runner/worker.py:138` 按 adapter 创建 AgentHttpAdapter；`runner/service.py:644` 注册 agent_http，`server/scheduling/service.py:123` 匹配冻结发现与 origin；旧 HTTP/Python 分支保留。
- `src/eyes/adapters/agent_http.py:121` prepare 实际发现并核对冻结能力；`:228` execute 以原键/原截止提交，响应异常先查询；`:263` reconcile 获取状态和结果并核对身份/revision；`:284` 事件分页及去重，`:325` 产物下载/摘要核对，`:384` 按能力取消。接口路径不是 Runner 的占位声明。
- `src/eyes/agent_service/http.py:168` create_app 必须注入真实 execute/validate_input；`:212` 发布结果保留终态；`:260` 重启将未完成记录保守置 unknown，不重放业务；`:319` 提交先持久化去重映射，再投递回调。该服务 SQLite 只存外部协议状态，不替代平台 PostgreSQL。
- `integrations/mewcode/http_service.py:88` 实际调用 `bridge.execute`；`integrations/mewcode/bridge.py` 导入 MewCode 并运行 event loop/工具，回收实际工作目录文件。输出由实际运行产生，独立评分执行冻结代码产物，不是预设答案。

运行记录对应 6473c96：3/3、12/12，60 条 Eyes 事件中的 48 条外部事件、8 份产物有两侧匹配记录；导入/目标/评分器/实验身份、独立评分 trace、冻结清单、认证及范围拒绝都可追溯。缺少/错误 Agent 凭据 401、Eyes read 发布 403、错误目标 Runner 读产物 403；同键冲突 409，不新增外部 run。已完成 Agent 重启保持原终态，不能充当活动 Runner 崩溃验收。

MewCode 明确 cancellation=false/resources=false，拒绝端点 422 已运行；这证明负向按声明行为，不证明正向停止/上传。旧 Python/SDK 在兼容副本评分组合有实际记录，历史 Python Agent 闭环另有记录；旧通用 HTTP 的新版本运行未找到原始记录，不能把“保留代码”表述为全部旧接入已运行兼容。

## 任务二：未知操作安全核对

提交：`abd7e7c`；显式查询契约和历史目标投影随 `3aa7e50` 同步。

- `src/eyes/server/scheduling/service.py:610` sweep 在执行意图后租约失效调用 `mark_unknown:705`，清业务 lease，保留 reserved；未知工作不进入普通 queued 领取。
- `src/eyes/server/scheduling/reconciliation.py:22` 只领取具备能力的 unknown/reserved 原工作，固定 advisory lock 与 SKIP LOCKED 协作，持久化独立 token/expires/due/count；返回原 Attempt、CaseRun、键和已知远端身份，不创建业务 Attempt。
- `src/eyes/runner/reconciliation.py:20` 只 GET capabilities/by-key；不调用 prepare/execute/cancel/cleanup。`:64` 保存 assignment/result journal，经原 outbox 补传；没有 result 的崩溃查询由数据库租约安排，不能恢复成业务重跑。
- `server/scheduling/reconciliation.py:117` 提交绑定 claim/凭据/Runner/Attempt，校验 task/attempt/run、revision 及同 revision 内容；重复同摘要幂等，不同摘要冲突。过期/被接管/人工 resolve 后只追加 late 事实。
- `contracts/agent_protocol.py:117` AgentResult 校验明确终态须 stopped_confirmed 和 completed_at；有效查询终态才调用 `scheduling/service.py:547` resolve，更新原操作、追加来源及 previous_result，释放原额度。查询失败、非终态、unknown 即使报告停止仍不自动释放。
- `migrations/versions/0005_reconciliation.py:14` 只新增默认 `{}` 的 JSONB 核对状态。后续已实际运行独立升级，历史副本记录没有改写原执行、Manifest、ScoreRun。没有历史 unknown 的实际自动领取证据。

核对后的证据保持 partial，清理未知不改为成功；远端快照里的产物描述不算 Eyes 已登记证据。历史评分/报告不自动重写，后补证据须显式 rescore。原 Runner 迟到业务结果被 `service.py:311` lease/token 或完成摘要规则隔离。以上是代码事实，竞争、停止确认、只释放一次、查询退避跨进程重启均仍需真实 PostgreSQL/Agent 故障运行证据。

## 任务三：显式版本和兼容边界

提交：`3aa7e50`；兼容补充 `0a6b74d`。

- `src/eyes/contracts/base.py:36` 普通 Contract 必填 schema_version；`server/api/middleware.py:29` 显式兼容头与管理员截止双条件；`server/config.py:36` 截止上限固定 2026-11-01T00:00Z（北京时间 08:00）。版本错误、未知字段仍拒绝。
- `contracts/agent_protocol.py:37` 独立 Message 必填 protocol_version；Git 对比确认外部模型及 agent-protocol-v1.schema.json 没随后三次提交改变。普通窗口不能补 Agent 版本。
- `contracts/base.py:55/:64` 只在持久化读取/指定迁移边界复制补普通版本，不改非版本值；`runner/outbox.py:39/:163` 持久化发送投影与新入队严格校验区分。`cli/main.py:27` 提供 migrate-schema，不覆盖原文件，JSONL 逐行整体校验。
- 3aa7e50 同步 Web 实验/批次/目标/评分器/resolve/比较的顶层及嵌套版本，CLI、Runner、SDK、规则评分、Deta/MewCode 构造和发布脚本；JSONL 原任务已有显式版本，未改评测用例。
- `server/scheduling/service.py`、`evaluation/service.py:126` 和核对领取对历史 Target/Scorer 出站投影；发布/实验摘要不在存储中重写。版本任务无新数据库结构迁移；桥接/评分器代码改变须发布新摘要，不冒充旧冻结插件。

真实 API 记录支持旧请求和显式副本的同键规范化摘要一致；6 份原完成 journal 本来含版本，其严格 API 的网络补传不是“真正缺字段材料”验证。新 Supervisor 配旧 Worker/SDK/冻结评分器、旧 Runner 完整组合均有运行证据，不能推广到旧插件直接加载新严格 SDK 或外部 exporter。副本前后原结果/清单/评分相同；未调用创建报告接口，本轮也未改历史报告，但没有全面报告数据库前后摘要核验材料。

## 按优先级排序的缺口

| 优先级 | 类型、位置与触发条件 | 影响 / 下一步 |
| --- | --- | --- |
| P1 | 运行验收阻塞：任务二上述 claim/submit/Runner/sweep，在活动 Runner 退出、查询/API 故障、两 Runner 竞争、旧 Runner 迟到时 | 不能确认未知副作用不重跑及额度只释放一次；独立真实环境补齐原操作/状态/额度/来源/退避证据，失败必需项优先修复 |
| P1 | 当前 Docker Linux 引擎不可达，涉及独立 API/Runner/Agent 故障验证 | 本轮运行验收无法补齐；恢复可用环境且核对原服务隔离后再开展，不能在原任务上故障注入 |
| P1 | BUG-001 四项计划中的单项失败继续发送路径（outbox），缺少行为记录 | 证据/完成交付可靠性未充分验收；按原计划补齐，不重复实现新功能 |
| P2 | BUG-002/003/004：孤立文件隔离、readiness 发布路径、Web ScoreRun 绑定 | 历史 Linux 200/Windows 503 可作为 readiness 子集证据，仍缺受控写入失败/探测清理及浏览器完整报告证据；原计划保留 |
| P2 | agent_http cancel/resources 正向路径、提交响应丢失、旧通用 HTTP 新版本运行；缺支持这些能力的真实目标或原始证据 | 任务一完整能力覆盖无法确认；不能用 MewCode 未声明能力或模拟输出补验收 |
| P2 | 任务三缺版本历史 outbox/快照、更早默认字段重放、外部 exporter/旧客户端、当前 Web 实际提交 | 兼容承诺应保持已文档化的限定范围；先找真实旧材料/环境，缺材料明确无法确认，不人工删除版本伪造历史 |
| P2 | 同目标版本改善/退化及 gate pass；完整 ready 产物/评分/报告备份恢复 | M3/M4 缺关键结果，按后续提示词分别验收 |
| P3 | 参考服务无限保留、核对 journal 保留及容量/长期运行 | 延续现有运维目标；本轮不压测、不扩展存储/保留功能 |

## 是否进入下一阶段

可以进入**下一轮验收和必要修复**，不具备宣布 M0～M4 完整验收或发布完成的条件。先关闭任务二安全运行门槛；任务一/三仍维持限定范围。以下三项按顺序开展，第一项将安全恢复必需项与已有四项 Bug 行为验收一起收口；后二项保留真实版本回归与完整备份恢复。不是重新列统一协议、恢复机制或版本迁移为新功能。

## 可直接使用的三个提示词

### 1. P1：安全恢复与已有四项 Bug 行为验收

> 负责 Eyes 安全恢复及 BUG-001～004 行为验收。先读 AGENT.md、README、docs/PLAN.md、docs/acceptance-review-20261011.md、docs/unknown-recovery.md 和 docs/bug-fix-plan.md，核对当前提交、环境及既有证据。首先在独立 PostgreSQL/证据卷/Agent 状态/端口/Runner 状态和限定目标凭据下，用现有真实 Agent、原任务和评分器验证活动 Runner 整体退出、租约失效、原键恢复、查询失败保留 unknown/额度、可信终态只释放一次；覆盖两个 Runner 竞争、重复核对、查询租约接管、旧 Runner 迟到、API 中断补传、持久化退避和服务重启。证明原 Attempt/远端 run 不增加、不重新执行未知副作用。必需项失败优先修复，再按原计划验证单项上传失败不阻塞其他项、崩溃孤立文件保留/隔离、readiness 200/503 和无探测残留、Web 显式新 ScoreRun 创建报告且默认/旧报告不变。缺服务/真实能力/旧材料明确阻塞，不用模拟结果替代。不要新增或修改测试文件、用例、fixtures、mocks、模拟数据；不干扰原任务，不覆盖原数据，不提交秘密。允许修复验收确认的业务缺陷并同步必要文档，检查后相关修改独立 commit/push 当前分支，不强推。报告实现/静态/真实运行/待验证四层证据。本轮不做版本回归或完整备份恢复，不宣称 M0～M4 全部通过。

### 2. P1：同一真实 Agent 的改善与退化回归

> 负责 Eyes 同目标真实版本回归验收。先读 AGENT.md、README、docs/PLAN.md、docs/acceptance-review-20261011.md、comparison/platform 文档及既有运行记录，确认第一项安全恢复必需门槛已通过，未通过则先报告阻塞。选择同一个真实 Agent 的可追溯不同版本，冻结同一既有测试集、评分口径、配置与可比环境，实际得到至少一项改善和一项退化；不用不同 Agent 的通过率或预设输出替代版本变化。若缺真实版本先报告并准备具体候选，不擅改外部 Agent 核心来制造变化。核对逐用例执行、独立评分/引用/固定清单、可比性及分母，默认最早评分、显式新评分选择和旧报告不变，CLI gate 0/1/2/3 按真实条件验证。只用已有用例/评分器，不新增或修改测试、fixtures、mocks 或模拟数据。独立环境保留失败和原始记录，发现 Eyes 缺陷可修复；只提交必要相关源码/文档，检查后独立 commit/push，不强推、不提交凭据/私有数据。报告待验证边界，不提前宣布 M3 或其他里程碑完整通过。本轮不开展备份恢复或新功能。

### 3. P2：当前版本完整证据备份与恢复

> 负责 Eyes 当前版本完整备份恢复验收。先读 AGENT.md、README、docs/PLAN.md、docs/acceptance-review-20261011.md、docs/platform.md、operations/backup 源码、迁移和已有验证记录。使用可追溯真实实验材料，包含 ready 产物、事件、Manifest、ScoreRun/Score、固定报告及 unknown/额度记录；只在独立副本和空恢复目标验证现有备份/恢复工具与 0005 升级，不覆盖原数据库/证据卷/Runner 状态。记录版本、命令、失败和原始响应，按身份、数量、内容摘要/字节、评分引用及报告前后比较，运行 audit；检查恢复后旧 Runner 凭据/领取隔离、未知额度保留和读取权限。不要把冷态复制、无产物恢复或工具代码存在称为完整备份恢复通过。缺材料/服务明确待验证，不造模拟证据、不新增或修改测试/用例/fixtures/mocks、不压测、不安装无关依赖。发现确认的恢复缺陷可修复并同步必要文档；检查后独立 commit/push 当前分支，不强推，只提交相关源码/文档，不提交数据库、备份、日志或秘密。明确 M4 尚缺的干净部署/权限/容量等项目，本轮不扩展功能。

本轮文档交付检查为 diff 空白及修改文档的本地链接存在性；不是服务运行验证。提交/推送结果以本轮最终 Git 输出为准，不在本页填写尚未产生的自身提交哈希。
