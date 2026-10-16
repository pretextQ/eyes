# 编码回归交付复核与最小真实评测准备

日期：2026-10-16（Asia/Shanghai）。状态：任务1交付复核、任务2方案准备完成；
任务3尚未获授权，未开始真实评测。本文件不把准备状态写成运行验收。

## 交付复核

本轮开始时为 `main`，工作区干净。`git fetch origin` 后，本地HEAD与origin/main均为
`b4127d98fbc4dc6ecb98501612a23f63dc30e8dc`。此前五次提交均已推送并包含于main：

| 提交 | 交付 |
| --- | --- |
| 3b1e9fe | chunk、评分基础设施、离线校验器及入口 |
| 3a58bcf | 整数CLI |
| 3e9878a | 多文件订单 |
| 41c9adc | 静态收尾，修正函数输出/导入空白规则 |
| b4127d9 | 专项授权后的运行材料、实际worker验证及运行问题修复 |

已重新阅读AGENT、README、architecture、修订草案，以及coding目录的数据、评分器、
校验器、验证驱动、候选和说明；对照Runner、评分服务及catalog源码核查契约映射。
草案仍保留当时的“尚未实施”及旧授权背景，实际完成状态以
[实施记录](coding-regression-implementation-20261016.md)和当前源码为准，不改写历史草案。

| 核查项 | 本次源码复核结论及边界 |
| --- | --- |
| 三题公开规则/数据 | 仅chunk、整数CLI、订单三题；prompt/files提供业务规范及初始文件，expectations只供评分；环境为空、单轮。13/5/16组，18/17/78条件，各100分，未扩展其余六题 |
| 精确计分/诊断 | 整数分值累加；复合组全过才计分；100才pass；逐条件pass/fail/not_run/error保留，reason为有界完整JSON；严格比较返回类型、JSON字段和整数，拒绝布尔冒充整数 |
| 函数与副作用 | 检查输入前后结构，chunk外层/块身份及块间别名；允许元素深拷贝；调用期间少量输出不引入隐藏扣分规则，独立导入检查仍要求静默 |
| 多文件及-I | 冻结路径白名单；重建money/order/main；可信启动器先载入所需标准库，再仅在候选子进程加入项目路径；命名导入及runpy脚本身份/argv；父评分进程不导入候选 |
| 证据/错误分类 | 唯一精确名称、授权引用、可读字节及size/SHA-256；缺失/歧义/过期保守insufficient_evidence，不采信来源不明missing事件；完整性/本地下载材料损坏或配置错误为error；候选行为/语法/超时/超量为质量失败 |
| 限额及回收 | 每候选3秒，双通道各64 KiB；每波最多8个监督进程；阶段60秒且预留deadline末10秒；Linux subreaper、控制管道EOF、killpg/wait；非安全沙箱，不覆盖恶意另建会话 |
| Runner示例 | 两份MewCode示例均配置coding_regression入口及45秒CPU/512 MiB AS/1 MiB FSIZE；是评分绑定示例，不能当作本轮trae部署配置直接运行 |
| 平台边界 | Runner仍先下载全部清单产物；仅要求input不保证按文件等待；410特定错误与其他下载故障由Runner前置分类；不改变公共契约、核心Runner或数据库定义 |

结论：本次未发现需要修改评分器源码的真实评测阻断问题，不为复核制造修复提交。
这不是全输入域正确性证明，也没有把尚未运行的端到端路径升级为通过。

本次静态命令均通过：

```powershell
uv run --no-sync python -m integrations.coding.validate
uv run --no-sync ruff check src migrations integrations/coding
uv run --no-sync ruff format --check src migrations integrations/coding
git diff --check
```

已有运行证据：实施记录与本聊天先前实际工具输出记载三题正确实现、典型错误、证据分类、
超时/超量、预算、派生进程及真实ProcessWorker强杀路径的定向验证；验证驱动和人工候选
已在此前专项授权下提交。仓库内是汇总记录和可复用驱动，不包含独立保存的原始stdout日志。
本次未重跑已经完成的完整故障矩阵，未新增或修改测试、fixtures、mocks、snapshots。
新三题仍没有真实Agent结果。HTTP下载/410重试、资源耗尽压力和长期负载仍未独立验收。

## 已核查的目标与环境

推荐本轮只选已有trae-agent，统一HTTP接入，模型 `mimo-v2.6-flash`，thinking enabled。
理由是已有独立模型/工具循环、相同prompt/files输入、原路径产物，以及请求前持久预算预留；
不需要修改外部Agent来运行这三题。第二个Agent和重复稳定性不在本轮。

| 项 | 本次只读核查值 / 拟冻结值 |
| --- | --- |
| Eyes执行源码基线 | b4127d98fbc4dc6ecb98501612a23f63dc30e8dc；本次后续提交仅文档 |
| trae源码 | D:\woker\trae，e6e03825d63ad764b4f2535e6db5cd10dcce1a97，工作区干净 |
| trae源码摘要 | src相对路径→逐文件原始字节SHA-256映射，sort_keys、紧凑JSON后SHA-256：9025cf1b1318359acc7ae78c82510555a949cc8f4908a77476e3b69e7f99b167（11个Python文件） |
| trae uv.lock字节摘要 | cadf58a8db2232cfc4a5dbdca9b2aa1b3874046a472c17fffa136b32768bf3a5 |
| trae镜像ID | sha256:0fa7d20782cc27f3ee92f70befca912582b47b5d4d1cb474fe58cf74e13e9407（trae-agent:local） |
| 控制/评分镜像ID | sha256:4775a9362087d827e6131e51be73c0e970aaf88b247d606c9142c892daa2ab82（eyes-clean-control:20261011） |
| PostgreSQL镜像ID | sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336（18.6） |
| Agent解释器/依赖 | 本次无网络只读信息容器确认Python3.14.8、httpx0.28.1、FastAPI0.143.0、Pydantic2.14.0、Uvicorn0.54.0；只输出版本，未启动serve/app |
| 评分解释器 | 本次无网络只读信息容器确认Python3.14.7；沿用已有定向验证环境 |

不能把上述宿主机源码版本称为已经运行中的Agent版本。历史停止容器
`eyes-dual-20261012-trae-fixed`实际仍绑定357d2ec的旧源副本及旧预算卷，本轮不启动、修改或复用它。
授权后使用当前拟选源码的新字节副本只读挂载，先核对实际import路径、逐文件摘要及能力发现版本，
三者匹配才发布目标。模型服务的同名别名不能冻结供应商内部权重。

本次未触碰现有运行中的 `eyes-capacity-web-20261014-api` 和对应pg，其他历史容器/卷保留。
本机已有模型凭据文件且对应字段非空，仅检查存在性，未输出值；有效性尚未发付费请求确认。

## 数据集及评分版本冻结

按当前Windows工作区实际字节复制到新只读快照，不用文本重写、换行转换或git archive替代复制。
启动后在评分容器内重新计算并核对，未来发布请求以实际容器字节为准：

| 对象 | SHA-256 |
| --- | --- |
| JSONL实际文件字节 / scorer.config.dataset_sha256 | 1c518bb176522261c3b98598f87d693d6f334a5e992fb695461a7cf0a10439c1 |
| scorer.py实际文件字节 / implementation_digest | 072411a84a3074ced8f736d5dc6f871d7404d258944aabbefc8aeb7eab38c5a1 |
| 平台数据集内容摘要 | 06c6e79a22a7cb626cefb66d0b62df811449ec633bf7c5cf5360bc10694ae839 |
| chunk CaseVersion内容摘要 | 83af6996b9ccd0438f4572643c1b34ada46e8fc8c27cb406aa9c3bf04f11c39e |
| int CaseVersion内容摘要 | a76914f852a8d330f7db8e462954cc408e53c744c9cfb8d43cdc6d9d3eba6d08 |
| order CaseVersion内容摘要 | d229ea07d5fb23fc0a6f14a28be0e1caacba8a4708e7c36369bb14aacf581ec4 |

平台摘要采用当前catalog的CaseDefinition序列化和domain.digest规则，本次只做内存计算，未导入。
Git LF blob的JSONL摘要为47335a91ca2ae2090a0288790952f1a4226d1bebbdc5f3a9cf5f158d7322eb8b，
scorer摘要为2b5c6fa9a12c2c6055c62ccf916b470670f09397fff378d99e4e3f40a98672b1。
它们与当前实际字节摘要不同，不能混用；这属于冻结/部署注意事项，不需要改评分器或历史版本。

拟发布新的 `coding_regression` ScorerVersion：config只含上述dataset_sha256；required_evidence
为["input"]；numeric含schema_version=1.0、minimum=0、maximum=100、direction=higher、
threshold=100、aggregation=mean；timeout_seconds=120，secret_refs为空。
不得使用旧deta_code发布脚本，它们会绑定旧三题和旧评分器。

## 一次最小评测的范围与资源

新实验只包含py-chunk-sequence、py-int-cli-errors、py-order-pricing-project，三题各一次。
repetitions=1、concurrency=1、timeout_seconds=480、evidence_wait_seconds=60、
attempt_selection=first_success；仅绑定本次新数据集/新目标/新评分器，无parent实验。
每题不自动重跑，不增加第二个Agent，不生成跨版本比较报告。

新控制环境设置EYES_MAX_PREPARATION_ATTEMPTS=1，避免默认3次准备尝试；执行和评分
全局额度均为1，项目及目标额度也为1。两个Runner分工：execute-only（1/0槽）和
score-only（0/1槽），后者不持有Agent或模型凭据。独立Runner身份、令牌、state_dir及卷。

按题使用 `eyes-runner --config <新执行配置> run --once`，核对该题终态、证据和评分后才
启动下一题的执行领取；评分同样独立单次领取。三个CaseRun已在同一新实验中排队，
单次领取失败不等于已经执行，不通过重复业务提交“补齐”结果。
确认的质量fail可继续下一题；执行错误、评分基础设施错误或证据不足则暂停后续领取。

| 层 | 拟配置与含义 |
| --- | --- |
| Agent服务 | 单进程/并发1；每题模型调用上限24、工具调用48；max_completion_tokens=4096（含思考）；请求120秒；工具默认20秒、允许工具参数指定至60秒（源码既有上限）；capture_model_io=false |
| Agent容器 | 非root UID10001，init=true，2CPU/2GiB/pids256；只给新状态卷和冻结只读源码，不挂宿主密钥目录或Docker socket |
| execute Runner | HTTP适配器；仅允许本Agent网络命名空间内127.0.0.1:19087；容器1CPU/1GiB/pids128，init=true |
| score Runner/worker | 容器2CPU/2GiB/pids256，init=true；worker CPU软45秒/AS512 MiB/单文件1MiB；候选各自相同软限，非进程树合计 |
| 单候选/插件阶段 | 墙钟3秒、stdout/stderr各64KiB、最多8个并行候选；阶段60秒并受request.deadline约束，预留10秒；题目保守预算12/12/40秒 |
| 证据下载 | Runner max_artifacts显式100，匹配Agent最多100个已采集文件；单产物上限32MiB；必要代码仍每文件256KiB；无关文件失败仍可能阻断评分 |

Agent能力拟沿用当前源码：session_isolation=true、environment_isolation=false、
cancellation=false、resources=false、events/artifacts=true；HTTP适配器提供幂等和原键核对。
resources=false指协议输入资源上传，不代表没有Docker资源限制。准备时仅核查源码，
最终能力必须以授权启动后的认证discovery为准。

证据范围为真实task/model/tool/artifact边界事件、最终输出及收集到的真实文件字节，
不是完整内部思考或全工作区无遗漏清单。trae排除__pycache__/.tmp，最多100文件、每文件8MiB；
收集结果不证明未列出的文件一定漏交。仅给Agent input.prompt/files，不暴露评分预期或验证材料。

## 费用预算及可约束范围

建议本轮三题共享总预算人民币1.00元（不是每题1元），新Agent状态目录的
AGENT_RUN_BUDGET_RMB=1.00，新budget_ledger.json从零开始并持久化；
仅一个服务进程访问，不允许复制服务绕过账本，不复用或重置历史预算。
最多72次模型调用尝试；实际发送付费请求数不高于该数，工具调用不直接调用供应商模型。
工具子进程使用精简环境，不继承模型Key；这也不把整个Agent容器变成任意恶意代码安全沙箱。
不为“测钥匙”额外发送模型请求；首个授权任务即为首个真实调用。

本次核对[官方按量价表](https://mimo.mi.com/docs/zh-CN/price/pay-as-you-go)：
mimo-v2.6-flash实时国内价为每百万token：未缓存输入1元、缓存输入0.02元、输出2元。
使用普通按量Key，不用Token Plan或Batch折扣；无供应商联网搜索/媒体服务附加费。
[官方API说明](https://mimo.mi.com/docs/zh-CN/api/chat/openai-api)确认max_completion_tokens
包含推理及可见输出；4096并不保证足够完成任务，截断如实记为执行结果，不临时加额度重试。

已检查trae model_client.py，预算不是仅在结束时统计：

1. 每个上游请求前，按序列化UTF-8字节数B预留
   `((4*B+4096)*1 + 4096*2)/1000000` 元；B上限128000，最大单请求预留0.524288元。
2. spent+预留超过1元即拒绝发送；pending预留先持久写盘，再发非流式请求。
3. 收到完整usage按缓存/非缓存/输出结算；未知usage、网络异常、429/HTTP异常保留未确认
   预留，后续付费请求被拒绝。当前_post不会自动重试模型请求。
4. 预算为服务整个状态目录的累计账本，不是每次Attempt重置。

这能约束本轮已知文本请求的客户端预留支出，依赖供应商遵守输出上限、usage及所选价率。
四token/字节是保守估算，不是供应商收费硬担保；费用未知不能报告为0。
账本锁仅在单进程生效，写入为临时文件加replace，没有数据库事务或断电财务保证。
当前没有核实供应商侧独立1元硬额度，不能承诺任意异常下账户绝不超过1元。
若用户要求供应商绝对封顶，应先具备相应Key/账户额度机制再评测，不以480秒超时代替费用限制。
历史旧三题的费用不外推为新三题的预计实际费用；新三题实际费用目前未知。

## 授权后预计操作与记录

本节全部是待执行步骤，不是已部署结果。拟命名空间/记录根：
`eyes-coding-real-20261016` / `D:\projects\eyes\data\coding-real-20261016\`。
若已存在则创建新的带序号命名空间，绝不覆盖。API拟127.0.0.1:18086，Agent内部loopback19087；
本次端口只读检查无占用，启动前仍需重查。PostgreSQL仅新Docker私网访问。

1. 保存本轮容器/活动工作基线；以已确认版本制作只读字节快照，记录Python文件映射、
   digest、image ID、依赖清单和配置。容器实际加载路径/摘要匹配后才能进入付费阶段。
2. 在新命名空间创建PostgreSQL卷、证据卷、Agent状态/预算卷及两个Runner状态卷；
   新库只应用现有迁移到0007，不新增/修改schema定义、不接入历史数据库。
   此项新库初始化包含在待确认的服务授权中，当前未执行。
3. 启动新PostgreSQL、API、Scheduler；API/调度全用相同冻结src及新库。新项目bootstrap，
   分别签发管理、读取、execute-only、score-only凭据；私有文件只保存到忽略目录，不打印令牌。
4. 以新HTTP凭据、新预算和本轮参数启动一个trae服务；现有模型密钥仅进入该Agent。
   新执行Runner与Agent共享网络命名空间以满足loopback HTTP要求；控制链路走新私网。
   认证discovery和只读模型/工具源码校验不调用模型。
5. 通过认证公开API发布新目标、POST /v1/datasets/import导入原样三题、
   POST /v1/scorers发布上述冻结新评分器；保存服务端UUID及内容摘要并逐项核对。
   对新实验使用持久唯一Idempotency-Key，POST /v1/experiments只创建一次。
   网络重传复用原键；不生成新的业务重跑键。
6. 按前述单次领取策略运行三题，逐题保存Attempt、ScoreRun、冻结Manifest及版本、
   真实原文件、元数据/下载字节size及SHA-256、引用归属、Runner journal/outbox及费用账本。
7. 输出只含脱敏汇总的验收文档；不发布比较报告，不提交原始请求/响应、产物、环境文件或凭据。
   检查后按Conventional Commits提交并推送独立文档/修复；原始材料留在忽略目录及新卷。

记录目录拟分为sources/、config/、catalog/、requests/、attempts/、scores/、manifests/、
artifacts/、logs/、budget/及service-state/；恢复时复用原idempotency key、原Agent数据库、
原预算账本及Runner状态，不清空unknown。开始前记录初始账本，结束记录spent/pending/usage，
计费汇总同时列实际usage计价与未确认预留；供应商账单未取得则注明未做账单对账。

## 停止条件与结果口径

- 版本、字节摘要、能力、初始账本或价率不匹配：付费前停止；不默默更换版本/模型/预算。
- 准备失败、预算拒绝、网络/usage未确认、活动unknown、评分error或证据不足：停止后续领取，
  保留已发生事实及额度，不重跑、不追加次数；根据原键只读查询处理未知，不把进程退出当成远端停止。
- 单纯代码质量fail是有效结果，可继续已授权剩余题；不自动修复Agent产物后再测。
- 三次执行超时配置合计24分钟，评分另有3×120秒；这不是整轮停止上限。
  运行观察超过40分钟时停止新领取、取消尚未开始项并进入状态核对；不强杀并宣称已停。
- 正常完成后，先核对业务/工具停止、活跃/unknown工作、预算pending、outbox及证据封存。
  正常停止本轮Runner、Agent、Scheduler、API和PostgreSQL；不删除卷或恢复材料。
  unknown或仍有活动调用时只停后续调度、保留必要核对组件并报告，不能声称服务已安全全停。
- 不启动maintenance，不清理历史数据；既有运行中的capacity-web API/pg保持原状态。

最终报告计划3、实际执行成功数、有效评分数、pass/fail、执行失败/超时/取消/unknown、
评分error、证据不足、skipped及N/A各自计数，并给出未解决项、实际费用/未确认费用、
目标/评分/环境版本。不能把执行成功等同质量通过，不能排除缺失项抬高均分或通过率。
单次三题只说明这次结果，不宣称稳定性，也不作为跨Agent或同Agent版本改善/退化证据。

## 待用户一次性确认

1. 是否选择trae-agent e6e03825d63ad764b4f2535e6db5cd10dcce1a97，模型mimo-v2.6-flash、
   thinking enabled及本文件冻结环境？
2. 是否确认仅三题各一次、并发1、480秒/题、模型24次/工具48次/输出4096的上限，不追加目标或重跑？
3. 是否确认三题共享总预算1元，接受上述持久客户端预留约束及其供应商侧硬封顶限制？
4. 是否授权在全新命名空间启动必要服务、初始化新库的既有schema、创建新项目/凭据、
   发布新目标/评分器、导入新数据集、创建唯一实验并按计划执行及正常停止？

在收到明确授权前，仅保留本方案和复核文档，不进入任务3。
