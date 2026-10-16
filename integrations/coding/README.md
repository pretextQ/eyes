# 编码回归扩展

本目录实现独立的 `coding_regression` 评分插件和产品评测数据；不改变旧三题、
`deta_code` 或历史评分。来源为[修订草案](../../docs/coding-regression-review-proposal.md)，
本轮用户授权优先于草案中的旧授权描述。其余六题继续为候选。

当前包含 `py-chunk-sequence`（13 个评分组，18 个独立条件进程）。JSONL 的
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
四个并行候选槽位，阶段至多60秒，服从 request.deadline 并预留10秒。
每个条件包括 .5秒回收和 .5秒启动余量，离线预算以每波4秒计算，最多52个条件。
调度抖动/下载延迟仍可能耗尽预算，此时 error，不能把未运行条件记成质量失败。

独立监督进程脱离 worker 进程组，持有父控制管道，EOF时杀死候选进程组。
Linux subreaper 回收候选后代；正常、异常、超时和输出超限路径均 killpg/wait，
无法确认回收返回 error。恶意候选新建会话、更强沙箱和树总额度不在本轮范围。
worker 被强杀、进程回收和资源参数均需要运行验证，静态实现不代表验收通过。

本轮不导入数据、不发布评分器、不运行真实 Agent、不创建实验或比较报告。
评分器运行验证须使用已有获授权材料；不能自行新增仓库测试、fixtures、mocks、
snapshots 或内联自测。真实 Agent 评测另行明确目标版本、范围、次数、并发、超时及费用。

任务1静态检查（2026-10-16，Windows/PowerShell）：`uv run --no-sync python -m integrations.coding.validate`、`uv run --no-sync ruff check src migrations integrations/coding`、`uv run --no-sync ruff format --check src migrations integrations/coding` 和 `git diff --check` 通过。18个条件，保守预算20秒。尚未执行候选代码或评分器运行验证。
