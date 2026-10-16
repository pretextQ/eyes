# 编码回归扩展

本目录实现独立的 `coding_regression` 评分插件和产品评测数据；不改变旧三题、
`deta_code` 或历史评分。来源为[修订草案](../../docs/coding-regression-review-proposal.md)，
本轮用户授权优先于草案中的旧授权描述。其余六题继续为候选。

最新交付复核及待授权的最小真实评测方案见[评测准备](../../docs/coding-regression-preflight-20261016.md)。
后续用户授权后的[trae单次真实评测](../../docs/coding-regression-real-acceptance-20261016.md)：
chunk/int执行与独立评分通过；订单因4096 token输出截断执行失败，无有效质量评分；未重跑。
以下各任务段落按实施时序保留当时状态，最新运行范围以任务4及其实施记录为准。

当前包含 `py-chunk-sequence`（13组/18条件）、`py-int-cli-errors`（5组/17条件）及 `py-order-pricing-project`（16组/78条件）。JSONL 的
prompt 是公开业务规范，expectations 冻结检查 ID、具体输入、预期、权重及分组。
每个条件在新目录、新进程运行；复合组全部条件通过才获得该组整数分数。
条件失败不阻断其他条件；未执行明确记为 not_run。100 分才 pass。
函数结果递归比较精确类型；检查输入不变、返回块身份、块间别名及导入静默。

在 Windows PowerShell 的项目根目录运行静态检查：

```powershell
uv run --no-sync python -m integrations.coding.validate
uv run --no-sync ruff check integrations/coding
uv run --no-sync ruff format --check integrations/coding
```

离线校验器只读取数据并校验契约、路径白名单、检查种类、ID、整数权重及最坏进程预算；
不执行候选、不调用 Agent、不访问 API 或数据库、不发布任何记录。
公开规范与检查语义仍需人工审阅，配置校验不证明评分器行为正确。

未来另获发布授权时，使用校验器输出的 config（数据集 SHA-256）、numeric、
required_evidence 和 timeout_seconds。Runner 示例包含绑定入口；自动插件摘要覆盖
单个 scorer.py，数据集另外通过 config 摘要冻结。不得复用旧评分器版本。

必要文件必须有唯一精确路径名、授权的 artifact 引用、完整字节数及 SHA-256。
仅重建每题白名单中的代码，其他产物不会成为运行依赖；保留名由白名单固定为本题
指定模块，标准库、检查器和内部目录均不开放为候选路径。代码上限每文件256 KiB。
缺失、歧义、不可用/过期代码为 insufficient_evidence；不凭 artifact.missing 或
output.files 推定漏交。当前没有可靠的缺失事件来源及引用绑定，因而不实现猜测性零分。
完整证据下语法、导入、行为、超时、输出超限为 completed/fail；配置、完整性、
解释器/监督器启动、回收或检查器故障为 error，无分数。平台下载前置故障仍由 Runner 分类。

候选目录、可信启动器和证据目录分开；使用 Linux 评分解释器 `-I`，先载入检查器
标准库，再显式添加项目目录，仅在候选进程导入项目。目录隔离不是安全沙箱。
不传递宿主机或 worker 的密钥环境。诊断保存组得分、所有条件状态和固定原因码，
不保存候选输出/异常正文；完整 JSON 超过5000字符时返回 error，不截断 JSON。
引用严格取自本次 evidence.references。

进程资源配置：每个候选墙钟3秒，stdout/stderr各64 KiB，超限立即停止；
CPU软限制45秒、地址空间512 MiB、单文件1 MiB，均为每进程限制，非进程树合计。
八个并行候选槽位，阶段至多60秒，服从 request.deadline 并预留10秒。
每个条件包括 .5秒回收和 .5秒启动余量，离线预算以每波4秒计算，最多104个条件。
调度抖动/下载延迟仍可能耗尽预算，此时 error，不能把未运行条件记成质量失败。

独立监督进程脱离 worker 进程组，持有父控制管道，EOF时杀死候选进程组。
Linux subreaper 回收候选后代；正常、异常、超时和输出超限路径均 killpg/wait，
无法确认回收返回 error。恶意候选新建会话、更强沙箱和树总额度不在本轮范围。
worker强杀、进程回收和资源参数已有本轮定向运行验证，实际范围见实施记录；静态实现和局部验证不代表完整验收。

本轮不导入数据、不发布评分器、不运行真实 Agent、不创建实验或比较报告。
用户已专项授权本轮离线验证驱动与候选材料，见verification目录；授权不扩展至其他仓库测试或历史运行材料。真实Agent评测另行明确目标版本、范围、次数、并发、超时及费用。

任务1静态检查（2026-10-16，Windows/PowerShell）：`uv run --no-sync python -m integrations.coding.validate`、`uv run --no-sync ruff check src migrations integrations/coding`、`uv run --no-sync ruff format --check src migrations integrations/coding` 和 `git diff --check` 通过。18个条件，保守预算20秒。尚未执行候选代码或评分器运行验证。

任务2：整数 CLI 冻结 int-valid/empty/large/invalid/import 五组，分值30/10/10/40/10。合法条件含正负混合、显式加号、前导零；大整数含20位及100位边界；非法条件分别运行空串、正负符号、前后空白、下划线、小数、全角及阿拉伯数字、合法/非法混合。每个条件独立新进程，保守预算20秒。CLI实际以 `runpy` 设置脚本身份/argv运行，比较退出码、原始错误通道和严格JSON（拒绝重复键、NaN/Infinity、额外字段、布尔冒充整数及额外日志）。导入使用非法CLI参数检查无副作用。

任务2静态检查（2026-10-16，Windows/PowerShell）：同任务1的离线校验、Ruff检查/格式检查、`git diff --check` 通过。尚未执行评分器或真实 Agent。数据集内容变化后必须使用新的config摘要及评分器版本。

任务3：订单保留 money.py/order.py/main.py 原路径。函数分别加载命名模块，CLI以 main 的脚本身份真实运行；`-I`下显式项目路径由可信启动器加入，父评分进程不导入候选。每个CLI条件在独立候选目录生成 `order input.json`（输入路径不覆盖代码，候选目录与可信启动器及只读证据目录分开），覆盖带空格路径、取整及先折单价后乘数量、参数数量、缺文件、非法UTF-8、JSON语法、顶层/嵌套重复键、NaN/正负Infinity、对象形状及非法业务值。三模块分别在带非法CLI参数的进程导入。函数条件覆盖空/全折扣、金额/数量/折扣边界、布尔和非整数、空订单非法折扣、列表及行形状和输入不变。

每个条件都是独立进程，分组仅用于全过计分，不共享候选模块缓存。订单78条件的保守预算为40秒；为容纳明确展开的矩阵，候选并行槽从4调为8，仍为每进程资源限制（八个候选的内存上限之和可达4 GiB，并非保证会使用这么多）。当前chunk/int预算各12秒，尚待实际Linux容器验证。

reason.conditions 以 `[检查ID, 状态, 原因码]` 紧凑行保存；groups保存组ID/得分/满分。离线校验同时检查每题冻结权重序列、函数入口、生成输入路径及诊断上界。启动器在加载候选前写就绪标记；缺少就绪标记归基础设施错误，候选模块自身导入失败归质量失败。

任务3静态检查（2026-10-16，Windows/PowerShell）：离线契约/矩阵/预算校验、Ruff检查/格式检查及 `git diff --check` 通过。多文件加载、监督进程及资源参数尚无运行验收；不修改核心Runner、公共契约、数据库结构或外部Agent。

任务4静态收尾修正：公开规范只要求导入静默；函数调用过程中的输出在限额内不额外扣分，结果使用末尾可信检查帧读取。CLI和独立导入检查仍严格验证通道。该修正没有运行验证；环境、实际命令及材料限制见[本轮实施记录](../../docs/coding-regression-implementation-20261016.md)。

任务4运行验证：在Python3.14.7的本机Linux容器内，三题正确实现均100分；典型错误、证据缺失/损坏、预算不足、超时、输出超限及正常/异常/强杀后的回收均经独立驱动验证。真实ProcessWorker评分阶段（45秒CPU/512 MiB AS/1 MiB FSIZE）三题均100分；强杀后观测到的监督/候选/后代均已回收。运行发现并修复了后代持管道误判超时，以及限内存worker下额外线程池导致基础设施错误的问题。最终实现按波次并行启动最多8个监督进程，不增加插件线程。完整命令、失败历史及未覆盖边界见本轮实施记录；不代表真实Agent验收。

授权材料的复用入口为 `python -m integrations.coding.verification.run` 和 `python -m integrations.coding.verification.worker`，只在上述隔离Linux容器运行。worker驱动须同时将当前src只读挂载到镜像的/app/src，确保worker使用当前源码。需要Docker init回收孤立监督进程；候选后代由监督进程subreaper回收。
