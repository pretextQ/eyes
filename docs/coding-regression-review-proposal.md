# 编码回归数据集与评分口径扩展：待审阅方案

日期：2026-10-16（Asia/Shanghai）。状态：独立静态审阅后的修订草案，尚未批准实施。

本文汇总源码核查、历史验收文档与拟议方案，供后续实施和独立审阅。结论为**修订后可实施**：推荐先实施三题，其他六题保留为候选。文中的新任务、评分规则、文件和资源参数均为提案，不代表已经实现或运行验证。当前仅授权更新本文，不扩大到数据集、评分器、配置、数据库或评测执行。

## 1. 目标与授权边界

Eyes 是面向外部 Agent 的评测与执行观测平台。现有三题主要验证基本接入闭环，希望增加有代表性、难度分层、可客观评分的小型编码回归集。

已静态检查项目说明、契约、评分器、Runner、MewCode/trae 接入源码及历史验收说明；未执行评分器或真实 Agent。本次没有重新核验历史数据库或原始运行材料。本文修订不改变此前历史记录。

除更新本文外，继续保持以下边界：

- 不修改源码、数据集、评分器、配置、数据库或历史记录。
- 不新增或修改仓库测试、fixtures、mocks、snapshots。
- 不导入数据集、发布评分器、创建实验或报告。
- 不启动 Scheduler、Runner、外部 Agent、评分器或 maintenance，不调用模型。
- 不迁移、清理、合并、覆盖历史环境或凭据，不输出明文令牌和模型密钥。
- 不提交 Git、不推送、不创建 PR。

以下内容中的“源码事实”表示静态阅读所见；“历史文档记载”不代表本次重验；“推断”表示由实现推导的风险；“拟议规则”均待实现和验证。后续文件实施、评分器运行验证、真实 Agent 评测分别等待用户授权。真实评测还需要明确目标版本、范围、重复次数和预算。

## 2. 已核查现状

### 2.1 依据与入口

- [开发约定](../AGENT.md)、[项目说明](../README.md)、[架构](architecture.md)。
- [数据集契约](../src/eyes/contracts/dataset.py)、[评分契约](../src/eyes/contracts/scorer.py)。
- [现有三题](../integrations/deta/coding-smoke.jsonl)、[现有代码评分器](../integrations/deta/scorer.py)、[内置规则评分器](../src/eyes/scorers/rules.py)。
- [MewCode 接入说明](../integrations/mewcode/README.md)、[bridge](../integrations/mewcode/bridge.py)、[HTTP 服务](../integrations/mewcode/http_service.py)。
- [Agent 接入](agent-integration.md)、[统一 HTTP 适配器](../src/eyes/adapters/agent_http.py)、[评分服务](../src/eyes/server/evaluation/service.py)、[比较服务](../src/eyes/server/comparison/service.py)。
- [双 Agent 验收记录](dual-agent-acceptance-20261012.md)、[仓库 CI](../.github/workflows/ci.yml)。

另只读查看本机外部仓库：MewCode 位于 `D:\projects\MewCode`，trae 位于 `D:\woker\trae`。重点查看 MewCode 默认工具注册，以及 trae 的 `src/trae_agent/tools.py`、`workspace.py`、`http_service.py`。这些是本机源码核查，不代表当前运行服务加载了相同源码。

### 2.2 数据格式

JSONL 每行一个用例，显式提供 `schema_version: "1.0"`。包含稳定 `case_id`、`input`，以及可选 `expectations`、`tags`、`environment`、`artifact_requirements`、`preparation_version`、`environment_limitations`。

`input` 和 `expectations` 内部为业务载荷，核心契约不会自动验证编码检查项语义。导入检查重复 case_id 等错误，整体通过后发布，并保存用例和数据集摘要。`steps` 虽然预留，但当前拒绝非空值，首批必须为单轮任务。

源码事实：统一 `agent_http` 当前拒绝非空 `environment`，见 [实验创建校验](../src/eyes/server/experiments/service.py)。因此首批业务准备只用 `input.prompt/files`，`environment` 保持空对象，环境说明放入 `environment_limitations`；不能把运行限制填入 `environment` 后期待 Agent 自动执行。

### 2.3 三道现有题与评分边界

| case_id | 任务 | 实际评分检查 |
| --- | --- | --- |
| fix-mean | 修复平均数函数，空输入抛 ValueError | 三组平均数返回值、一组异常 |
| stable-unique | 保序去重，支持不可哈希元素，不修改输入 | 整数、空输入、字符串、嵌套列表四组返回值 |
| integer-cli | 整数求和 CLI，输出 JSON | 正数、负数、无参数、大整数四组 JSON 输出和退出码 |

现有评分器按名称查找真实采集代码，将单个文件复制为 `submission.py`，使用评分解释器和 `-I` 启动子进程。函数检查返回值或异常类型名称；CLI 检查解析后的 JSON 和退出码。每项五秒，全部检查通过才 pass，无数值分数，引用产物及预期证据。

未覆盖或存在的限制：

- 未检查 stable-unique 是否修改输入，也未检查完整文件修改范围。
- 未验证“先读源码”“Agent 自行运行验证”等过程要求。
- CLI 未检查 stderr、非法参数、输入文件或输出文件的业务结果。
- 仅重建单文件，无法原样运行多文件项目。
- 普通 Python 对象相等可能放过部分类型差异，例如 True 与 1。
- 未专门拒绝 JSON 重复键，没有权重、浮点误差或数值分数口径。
- 输出采集缺少专门限额；reason 最终截断可能损失诊断。
- HTTP 的 artifact.missing 可能混合未生成和下载失败，不能单独作为漏交证明。
- 现有发布配置要求 output/events/artifacts/sealed，服务端可能在插件执行前判证据不足，缺失产物判 fail 分支不一定可达。
- 独立进程及 -I 不是操作系统安全沙箱。

产品数据集的初始代码、验收输入和预期，与 Eyes 仓库自动化测试不同。现有 CI 的格式、构建、迁移和就绪检查不能替代真实 Agent 评测。

### 2.4 Agent 实际能力

| 项目 | MewCode | trae |
| --- | --- | --- |
| 业务输入 | prompt + files（相对路径到 UTF-8 文本） | 同左，拒绝额外业务字段 |
| 初始文件 | bridge 创建目录并写入 | Workspace 校验路径并写入 |
| 工具 | 默认注册读、写、编辑、Bash、Glob、Grep，受权限策略限制 | list_files/read_file/write_file/replace_text/run_python |
| 自检 | 可通过 Bash 运行 Python，受权限检查约束 | 运行已有 Python 文件并传 argv；无通用 Shell 或 stdin 工具参数 |
| 多文件 | 支持多个文件及子目录 | 同左 |
| 产物 | Python 按 artifact_requirements 采集；HTTP 遍历真实工作文件并保留相对路径名 | 遍历真实文件，排除 .tmp、__pycache__ 等 |
| 环境 | 当前接入使用本机 Linux 容器、Python 3.14 | 当前实现依赖 POSIX，已有 Linux 容器记录 |
| 隔离与取消 | 会话隔离；不声明环境隔离；HTTP 取消和资源上传能力关闭 | 同左 |

trae 当前读取上限64 KiB、写入上限256 KiB、工具运行最长60秒。任务应显著低于限制。多文件操作具备源码条件，不等于两种 Agent 已通过复杂任务验收。

历史文档记载：[双 Agent 验收](dual-agent-acceptance-20261012.md)覆盖旧三题、正常产物下载及定向恢复；[后续复核](acceptance-review-20261013.md)保留原评分和补充评分的区别。这些材料不能证明本方案九题的难度、耗时或正确率，当前本机源码也不证明历史或未来服务加载了相同版本。

## 3. 候选九题与推荐首批

保留原三题和 deta_code 评分器。九题作为候选池；推荐首批仅新增 **py-chunk-sequence、py-int-cli-errors、py-order-pricing-project**，配一个 coding_regression 插件，分别覆盖函数副作用、CLI 错误协议、多文件业务调用。其余六题不纳入首批数据集或发布范围。

以下简单／中等／较难是维护者暂定标签，不是 Agent 实测难度。它是小型 Python 标准库回归集，不代表大型仓库导航、依赖管理、服务集成或性能能力。整数 CLI 与旧题存在业务重叠，但新增词法、错误通道和导入检查；CSV 与 ledger 分别侧重表格解析和交易幂等，不视为直接重复。

每题满分100；首批以第4节矩阵为准，其余六题的分组只是待定建议。所有子条件及权重必须逐题冻结，不默认组内等分。

| case_id | 能力与业务要求 | 初始文件 → 产物 | 评分组及分值 | 暂定难度；批次 |
| --- | --- | --- | --- | --- |
| py-clamp-bounds | 修复闭区间限幅；low>high 抛 ValueError，相等合法 | bounds.py 错误表达式 min(low,max(value,high)) → 同文件 | 区间内20；上下越界30；相等/负边界25；反向异常25 | 简单；后续 |
| py-chunk-sequence | 列表分块，保序，末块可短；块长为非布尔正整数；不修改输入 | chunks.py 函数骨架 → 同文件 | 常规25；边界25；参数30；副作用20 | 简单；首批 |
| py-kv-config | 忽略空行及整行#注释，首个=分隔，键值去外侧空白，重复键后值覆盖；空键或缺=抛错；不处理转义和行尾注释 | settings.py 骨架 → 同文件 | 常规25；空白/注释25；重复键/含等号值25；非法行25 | 简单；后续 |
| py-merge-intervals | 合并重叠半开区间；相邻不合并；忽略零长区间；反向抛错；不改输入 | intervals.py 错误合并实现 → 同文件 | 乱序重叠30；相邻/零长25；嵌套/重复25；异常/输入不变20 | 中等；后续 |
| py-deep-config-merge | 双方值均为字典则递归，其余右侧替换；列表整体替换；不共享可变容器 | merge.py 浅合并实现 → 同文件 | 递归35；列表/标量替换25；空对象/类型变化20；无修改/别名20 | 中等；后续 |
| py-int-cli-errors | 合法参数为 ASCII [+-]?[0-9]+；成功输出计数和总和；非法参数stdout空、stderr固定错误行、退出2 | intsum.py 骨架 → 同文件 | 合法30；空/大整数20；非法词法及通道40；导入10 | 中等；首批 |
| py-csv-category-totals | 读取 category,amount_cents CSV；有符号整数金额，按类别汇总排序写JSON；失败退出2且不创建输出 | report.py、sample.csv → report.py；评分运行生成JSON | 汇总35；引号/Unicode25；仅表头/负数20；坏行/输出约束20 | 中等；后续 |
| py-order-pricing-project | 修复整数分金额取整，接通JSON CLI，同一业务函数可独立调用 | money.py、order.py、main.py → 三文件 | 金额35；验证/不可变性25；CLI正确25；CLI错误/导入15 | 较难；首批 |
| py-ledger-idempotent-report | JSONL交易：同ID同内容只记一次，同ID不同内容拒绝；账户净额排序输出，错误不留报告 | ledger.py、main.py、sample.jsonl → 两代码文件；评分运行生成报告 | 去重/冲突35；汇总25；空/负数/Unicode20；坏行/无部分报告20 | 较难；后续 |

源码事实：[实验契约](../src/eyes/contracts/work.py)只有实验级 timeout_seconds；[调度器](../src/eyes/server/scheduling/service.py)据此为所有 Attempt 设置截止时间，不能在同一实验内逐题设置180／300／480秒。推荐首批三题统一480秒，单目标并发1；这只是待验证参数。三次执行的配置时长之和为24分钟，不是整轮完成上限：排队、评分、清理、重试及 unknown 协调另计。实际耗时、模型调用次数和费用未知。如以后需要按难度设置超时，优先拆分数据集和独立实验，不在本方案中扩展契约。

共同约束：仅 Python 标准库，不依赖网络、额外服务或密钥；初始文件为小型UTF-8文本，使用相对POSIX路径；不强制Bash，允许临时自检脚本。首批不评分完整修改范围、代码审美、安全性或性能排名。

后续六题必须先补齐公开接口、输入域、类型和异常规则。尤其 CSV 需明确命令参数、JSON输出结构、金额词法、坏行及已有输出文件的处理；ledger 需明确交易字段、净额算法及“同内容”是解析后业务值还是原始文本。未完成对应验收矩阵前不得发布。

### 信息分离

- Agent 收到：完整业务规范、接口、错误行为、产物路径、初始文件。
- 仅评分器收到：expectations 中的具体验收输入、预期结果、检查ID、权重及评分配置。
- 不隐藏额外业务要求；隐藏验收数据不等于隐藏规范。
- 不把评分配置或预期复制到 Agent 工作目录；不把自述或工具调用次数作为通过依据。

## 4. 首批三题的公开规范与验收矩阵

以下为拟议任务说明，不是已导入的 JSONL。实施前需把每组展开为稳定检查ID、具体输入、预期、分值和进程分组，并由离线校验器检查公开要求是否都有验收项。复合项全部子条件满足才得分，但诊断分别记录子条件结果。只对公开输入域和规则评分，不以隐藏输入增加业务要求。

所有 prompt 均附加共同交付约束：最终运行只依赖列出的交付代码与标准库，不能依赖临时自检脚本；导入时不运行CLI，stdout/stderr均为空。评分会使用新输入和目录。不得依赖未公开的工作目录文件；不要求输出固定答案文件。

### 4.1 py-chunk-sequence

Agent prompt：

> 完成 chunks.py 中的 chunk(items, size)。items 必须是列表，否则抛 TypeError；size 必须是正整数，布尔值不算整数。size 类型不合法抛 TypeError，整数小于等于零抛 ValueError。即使 items 为空也须验证 size。返回由连续分块组成的新列表，外层和每个块均为列表，保持元素顺序，最后一块可以不足 size 个；空输入返回空列表。不得修改 items；外层和每个块均为新容器，各块互不共享列表容器，元素本身无需深拷贝。保留函数签名，仅依赖标准库。可以创建临时自检脚本，最终交付 chunks.py。

初始文件 chunks.py：

```python
def chunk(items, size):
    raise NotImplementedError
```

产物要求为 chunks.py；标签为 coding、implementation、boundary、easy；拟 preparation_version 为 coding-regression-v1；steps 为空。环境限制注明 Python 3.14 Linux、标准库、工作目录不构成安全沙箱。

| 检查 | 预期 | 分值 |
| --- | --- | --- |
| 常规两项 | [1,2,3,4],2 → [[1,2],[3,4]]；[1,2],1 → [[1],[2]]；均逐层断言列表类型 | 15、10 |
| 边界三项 | [],3 → []；[1,2],8 → [[1,2]]；[1,2,3],2 → [[1,2],[3]]；均检查类型 | 10、10、5 |
| 参数六项 | size=0、-1 分别抛 ValueError；size=True、1.5 分别抛 TypeError；items为tuple、None分别抛 TypeError。size四项同时覆盖空与非空列表 | 各5 |
| 无副作用两项 | 输入调用前后结构相等；修改返回块不改变输入且不同块互不影响 | 各10 |

返回容器必须为列表，不接受tuple或生成器；不要求深拷贝元素。语法错误、错误结果、候选程序超时是质量失败；下载或完整性问题不能算代码零分。

无副作用组同时覆盖嵌套可变元素的顺序、输入结构不变及块容器身份；不因候选选择深拷贝元素而扣分。导入无输出作为本题通过的共同条件，并归入常规组首项。

### 4.2 py-order-pricing-project

Agent prompt：

> 完成三个文件组成的小型订单计算程序。money.discounted_cents(price_cents, discount_bps) 返回打折后的整数分金额，采用四舍五入、半分向上；price_cents 为非负整数，discount_bps 为0～10000的整数，表示减免比例，两者均不接受布尔值。order.total_cents(items, discount_bps=0) 对每行先计算打折单价，再乘数量并求和，返回整数。items 必须为列表，每行必须是恰含 price_cents、quantity 的字典，两字段均为非负整数且不接受布尔值；discount_bps 遵循同一规则，空列表也须验证折扣。非法输入统一抛 ValueError，不修改输入。main.py 接收唯一一个UTF-8订单JSON文件路径，文件顶层必须是恰含 items、discount_bps 的对象，任意层级的重复键及NaN/Infinity均非法。成功stdout只输出一个仅含整数 total_cents 的JSON对象，允许JSON外侧空白，stderr为空，退出0；参数、文件读取、UTF-8解码、JSON或业务输入错误时stdout为空、stderr为 invalid order 加换行、退出2。导入三个模块时stdout/stderr均为空且不执行CLI。仅使用标准库，允许临时自检脚本；最终代码仅依赖交付的三个文件与标准库。

初始 money.py：

```python
def discounted_cents(price_cents, discount_bps):
    return price_cents * (10000 - discount_bps) // 10000
```

初始 order.py：

```python
from money import discounted_cents


def total_cents(items, discount_bps=0):
    raise NotImplementedError
```

初始 main.py：

```python
from order import total_cents


def main():
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main())
```

产物为上述三文件，评分时按原路径重建。Agent 无需生成固定订单答案文件。

| 检查 | 预期 | 分值 |
| --- | --- | --- |
| 取整三项 | discounted_cents(1,5000)=1；(3,5000)=2；(199,2500)=149 | 各5 |
| 总额两项 | 单价1、数量2、折扣5000→2；单价10、数量3、折扣0→30 | 各10 |
| 验证五项 | 合法空订单及全折扣为0；负金额/数量和折扣越界拒绝；money两参数、order折扣/每行字段的布尔及非整数拒绝，含空订单非法折扣；缺/多字段、非字典行及非列表items拒绝；输入不变。返回金额均断言整数且非布尔 | 各5 |
| CLI成功两项 | 含空格路径的订单文件→{"total_cents":2}；另一订单→30 | 15、10 |
| CLI错误及导入四项 | 无/多参数；缺文件、非法UTF-8、坏JSON、重复键及NaN/Infinity；顶层类型/字段错误和非法业务数据；导入三模块无stdout/stderr且不执行CLI。前三项逐一检查stdout空、固定stderr及退出2 | 4、4、4、3 |

拟议检查分别执行函数和CLI，每个检查进程使用新临时目录；同组多个子条件是否共享进程须冻结，不能把一个进程故障伪称为所有子条件已独立运行。两个成功CLI检查均检查严格结构、非布尔整数、空stderr及退出0。

### 4.3 py-int-cli-errors

Agent prompt：

> 完成 intsum.py。命令行接收零个或多个整数参数；每个参数必须完整匹配ASCII [+-]?[0-9]+，不接受外侧空白、下划线、小数、Unicode数字或仅有符号。本任务有效数值输入的数字部分最多100位，不规定超出该长度后的行为。成功时stdout只输出一个恰含 count、sum 的JSON对象，值均为整数，允许JSON外侧空白，stderr为空，退出0；无参数时两者为0。任一非法参数使stdout为空、stderr恰为 invalid integer 加换行、退出2。导入 intsum 时stdout/stderr均为空且不执行CLI。仅依赖标准库，可创建临时自检脚本；最终运行仅依赖 intsum.py。

初始文件 intsum.py：

```python
def main():
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main())
```

产物要求为 intsum.py；preparation_version、steps、环境声明沿用首批共同约定。

| 检查ID／组 | 验收条件 | 分值 |
| --- | --- | --- |
| int-valid | 正数、负数混合、显式正号、前导零；每组检查count/sum、非布尔整数、空stderr及退出0 | 30 |
| int-empty | 无参数→count=0、sum=0，通道及退出码同上 | 10 |
| int-large | 10000000000000000000与1→count=2、sum=10000000000000000001，通道及退出码同上 | 10 |
| int-invalid | 分别覆盖空字符串、仅符号、外侧空白、下划线、小数、Unicode数字及合法/非法混合；每项均检查空stdout、固定stderr和退出2 | 40 |
| int-import | 在独立进程导入模块，以非法CLI参数确认未执行CLI；stdout/stderr为空且退出0 | 10 |

每组内部全部子条件通过才得分，具体argv及进程分组在实施前冻结。支持的“大整数”验收限定在100位十进制以内，不要求绕过Python解释器的超长整数转换保护。

## 5. 评分口径与契约映射

### 5.1 分数与状态

数值语义：minimum=0、maximum=100、direction=higher、threshold=100、aggregation=mean。100分才pass；部分分用于定位退化。题目等权，难度层另列结果；分层展示方式尚需明确，不默认已有UI支持。

拟议规则：使用整数或精确有理数累计冻结分值，全部通过明确输出100，避免浮点累加低于门槛。100分只证明冻结检查通过，不证明所有可能输入正确。复合项诊断必须展示未运行、通过和失败的子条件，不能只返回组总分。

| 情况 | 契约表达 |
| --- | --- |
| 完整代码证据下行为、类型、退出码或结果错误 | completed/fail，有效部分分 |
| 全部检查通过 | completed/pass，value=100 |
| 评分配置、检查器、解释器启动、下载或完整性故障 | error，无value/verdict |
| 必要证据缺失或不可用，无法确认漏交 | insufficient_evidence，无value/verdict |
| 证据等待阶段取消，或插件明确决定跳过 | skipped，无value/verdict |
| 运行中评分取消、中断、租约丢失或外层超时 | 当前Runner/调度路径通常为error，无value/verdict；不承诺统一为skipped |
| 预先声明的不适用 | completed/not_applicable，无value |

Agent执行失败继续使用Attempt的failed/timed_out/cancelled/unknown，不伪装成代码质量零分。Agent正常结束但代码错误，是执行成功、质量失败。九题原则上均适用，能力不匹配不应随意用N/A消除失败。

源码依据：[评分契约](../src/eyes/contracts/scorer.py)、[评分入队及结果校验](../src/eyes/server/evaluation/service.py)、[Runner评分执行](../src/eyes/runner/service.py)、[调度恢复](../src/eyes/server/scheduling/service.py)。数值评分器的pass/fail必须带value和清单内引用；平台会验证数值范围、阈值和引用归属，但不会替插件验证业务检查是否正确。

候选语法错误、导入其应交付模块失败、返回错误、候选检查超时或超量输出，在检查器正常且必要证据可信时记为质量失败。可信缺失事实证明必需交付文件不存在时，首批约定该题completed/fail、value=0，并列出未运行检查；没有该事实则不能用0分替代证据不足。若评分器自身故障使必要检查未完成，返回error，不提交伪完整部分分。

### 5.2 行为检查

- 函数：真实导入调用，按需检查结构、类型、异常、输入状态和可变别名。
- CLI：实际启动，独立检查退出码、stdout、stderr。
- JSON：对象键序不计分，拒绝额外字段、重复键、额外日志及非法数值；整数不接受布尔值。所有影响通过的要求必须在业务规范公开。
- 文件：评分器创建新输入，运行候选程序，读取实际输出文件；不只检查名字存在。
- 多文件：仅重建冻结要求中的代码，保留路径；不使用Agent提供的预期答案。保留标准库、运行器及内部目录名，避免候选文件覆盖检查器。
- 不采用代码关键词、Agent自述或模型评价判正确；不设置微秒级性能排名。

### 5.3 多文件加载与目录边界

源码事实：旧评分器只把单文件复制成submission.py，再用-I和绝对文件加载；没有实现项目根目录与同级模块加载。仅重建money.py/order.py/main.py后直接运行 `python -I main.py` 不能作为本方案的加载实现，-I不会自动把脚本目录或当前目录加入模块搜索路径。

拟议实现：可信启动器使用评分解释器和-I启动，显式设置候选项目根目录的模块搜索路径；函数检查按正常模块名导入，CLI用runpy等方式设置脚本身份和argv后执行。不得把候选目录加入父评分worker的sys.path；先加载检查器所需标准库，避免候选文件遮蔽检查器。启动器故障归error，候选程序自身错误归质量失败。单文件和多文件均须在后续运行验证中核对此路径。

每个检查的候选目录与可信启动器目录、只读证据目录分开。只接受冻结清单中的相对POSIX代码路径；拒绝绝对路径、路径穿越、重复或歧义名称、内部目录和会遮蔽本题所需标准库的保留文件名。最终实现前冻结保留名清单；Agent仅被要求交付指定代码，允许的临时脚本不重建为运行依赖。目录与-I用于可复现加载，不构成安全沙箱。

### 5.4 资源与进程回收

源码事实：[Runner绑定](../src/eyes/runner/config.py)的cpu_seconds、memory_bytes及file_bytes在[worker初始化](../src/eyes/runner/worker.py)中分别映射RLIMIT_CPU、RLIMIT_AS、RLIMIT_FSIZE。它们不是整个候选进程树的合计CPU、内存或磁盘额度。平台评分截止时间从领取工作开始计算，包括获取评分输入、全部产物下载、启动和检查。

首批拟议参数：发布评分超时120秒；插件检查阶段至多60秒，并服从request.deadline，为诊断与退出预留至少10秒。每个候选检查进程墙钟至多3秒；stdout/stderr各64 KiB，按字节有界读取，超限立即停止检查。worker和候选进程各自的CPU软限制拟45秒、地址空间软限制拟512 MiB；磁盘单文件限制显式配置。不得称为总CPU45秒或总内存512 MiB。所有参数待Linux容器运行验证，下载延迟等仍可能导致评分error。

取消统一“最多12个进程”的未验证承诺：按第4节展开的真实检查数量冻结进程分组，并验证最坏墙钟预算。若无法在预算内完成，应调整预算或检查分组，不能悄悄省略检查。候选超时或输出失控使该检查失败；插件阶段预算耗尽、外层超时或未完成必要检查为error，未运行项不得记为已失败。

每个候选进程组必须在成功、异常、超时和输出超限后均终止并wait；仅等待组长退出不足以确认子进程停止。旧评分器候选进程使用start_new_session，不能认为外层worker进程组停止会自动回收这些独立组。实现前须选定可用的回收方式，例如由独立监督进程监测父进程控制管道并管理候选组；不能假定在评分插件线程注册信号处理器就能完成回收。正常停止路径须记录活动候选组、留出回收窗口；无法确认回收时不得报告成功。外层worker被强杀后的独立组回收仍需定向验证，未解决前不能宣称该项验收通过。恶意程序另建会话的停止保障、更强沙箱和进程树总额度不纳入首批。

### 5.5 证据门槛、缺失与引用

拟议发布配置为required_evidence=["input"]。这只放宽平台按证据类别判断的前置条件，插件仍须验证本题全部必要代码。pass必须具备所需代码的完整、可读、大小和摘要校验通过且名称无歧义的快照；无关事件缺失本身不阻断代码行为评分。

源码事实与限制：

- [missing_evidence](../src/eyes/server/evaluation/service.py)始终认为input可用，因此仅要求input不会因缺产物进入平台证据等待；不承诺evidence_wait_seconds会等到每个必要代码文件齐备。
- [Runner](../src/eyes/runner/service.py)在插件启动前下载、校验冻结清单中的全部产物，未按本题所需文件过滤。无关产物下载或完整性故障、数量超限仍可阻断评分；插件不能接管这些前置故障。首批接受此限制，不改核心Runner。
- Runner对不可用／过期证据及特定410响应返回insufficient_evidence，其他下载／完整性故障通常返回error。不得笼统承诺所有下载失败都进入插件或都属同一状态。
- 首次清单缺文件则保守记insufficient_evidence；迟到证据形成新清单，需显式rescore，不自动修正旧评分或旧报告。

缺失文件：可信事实确认不存在→质量失败；确认传输故障→评分错误；不能区分→证据不足。现有HTTP artifact.missing由下载成功后的名称集合推导，单独不足以证明未生成。Python本地Runner的不存在检查与HTTP语义不同，但不能只凭相同事件type推定来源可信。

**完整产物清单不是首批前置条件。** 必要代码齐备时可评行为，缺失原因不明时保留未解决项。若要求所有漏交稳定判fail，才需另立可信采集范围、采集完成声明、逐文件缺失／传输原因及来源绑定的改造范围。trae现有output.files来自已过滤、限量和限大小的采集结果，不等于无遗漏的工作区清单，不能据其未列出文件认定漏交。

沿用ScoreOutput的value/verdict/reason/evidence_refs。reason保存检查ID、得分、结果和有界诊断组成的紧凑JSON，总长度不超过5000字符，不硬截断JSON。通过和失败引用对应清单内产物、预期或可信缺失事件。现有契约没有独立逐项结果列表，首批不扩展契约；完整评分输出产物如有需要另行设计。

引用必须从request.evidence.references取值。源码事实：[证据视图](../src/eyes/server/evidence/service.py)的事件正文保留生产者event_id，而event:引用使用数据库记录ID，不能自行拼接或假定二者相同。首批主要引用代码产物和expectations；缺失事件若没有可靠的来源及引用关联，则返回insufficient_evidence。不得仅引用预期、自述或无关事件，把它当作实际行为或漏交证明。

## 6. 历史可比性

- 原三题和旧评分器不变时，保留原比较链路。
- 新题无旧基线；首批三题应独立建立基线，不能直接比较旧三题、新三题、合并六题或未来十二题的总通过率。
- 相同case_id不保证可比；prompt、初始文件、预期、标签、准备版本等变化可能改变用例摘要。
- 检查、权重、阈值、配置或实现变化，发布新评分器版本，不覆盖旧记录。
- 源码事实：当前比较器对超时、并发、重复次数、尝试选择、证据等待及目标capabilities变化追加不可比原因；评分器摘要变化同样不可比。目标配置变化主要产生警告，不能把配置变化后的结果默认归因于Agent版本。
- Python/容器环境、启动器及Runner资源限制变化未必全部被当前比较器自动识别。应记录解释器完整版本、容器镜像摘要、启动器／插件摘要、绑定资源配置和依赖标识；必要时纳入版本化评分配置，其他差异人工核对。元数据未被比较器校验时不能宣称环境已自动冻结。
- 当前rescore要求Attempt成功、没有待结束的初始证据等待，选最新清单，仍沿用原实验冻结评分器集合。评分retry仅对error开放，绑定原评分器和原清单。发布新评分器不表示可以直接用它重评任意旧实验。
- 比较默认选首个成功Attempt的最早评分；rescore不会替换默认最早记录。使用新ScoreRun需显式选择并生成新报告，旧评分和旧报告保持原样。证据过期后不能重评分。
- 环境改变后重新评分只表示旧代码在新评分环境的表现，不表示Agent在新环境重新完成任务；改变任务输入、初始文件或Agent执行环境后，应另建执行实验。
- 首批不迁移、不回填历史。

报告分别列出计划数、执行成功数、有效评分数、通过数、证据不足、评分错误和N/A。有效评分均分必须同时显示覆盖率，不能靠排除执行失败抬高结果。

上述细分计数、有效评分均分和难度分层为交付要求，不假定现有页面已全部支持；首批可通过结果导出和文档说明呈现，不把新增UI列为隐含前置。源码依据：[比较选择与可比性](../src/eyes/server/comparison/service.py)、[retry/rescore](../src/eyes/server/evaluation/service.py)。

## 7. 拟实施文件和验证边界

| 文件 | 拟议内容 |
| --- | --- |
| integrations/coding/coding-regression.jsonl | 首批三题、初始文件、公开规则、检查ID、评分输入、权重及进程分组 |
| integrations/coding/scorer.py | 首批函数/CLI/多文件评分、可信加载、有界输出、资源配置与进程回收、严格比较、状态分类；支持订单输入文件，不实现后续CSV/ledger输出报告评分 |
| integrations/coding/validate.py | 离线配置校验，不运行候选代码、不调用Agent、不发布记录 |
| integrations/coding/README.md | 题目、评分、证据、版本及运行边界 |
| integrations/mewcode/runner.example.toml | 新评分插件示例 |
| integrations/mewcode/http-runner.example.toml | 新评分插件示例 |
| docs/agent-integration.md、README.md | 新入口与边界说明 |

推荐范围从静态实现看不需要数据库结构迁移、公共契约变化、核心Runner改造或外部Agent修改；不改旧三题、deta_code和历史发布脚本，不增加依赖。这里“无需改数据库结构”不等于发布和执行不写数据库：未来导入、发布、实验和评分都会新增记录，仍须单独授权。本次只更新本文。

若后续要求按用例超时、按需下载产物、所有漏交稳定判fail、完整逐项结构化结果或进程树总资源额度，应重新界定实施范围，不能把这些能力悄悄包含在“不改核心”的承诺中。

后续分三步分别确认：

1. 文件实施及静态验证：只实施首批三题；先冻结公开要求→检查ID→输入/预期→权重及进程分组的矩阵。检查JSONL、唯一ID、路径、规则语义、权重总和、最坏评分预算和文档链接；注意现有CI Python lint主要覆盖src/migrations，integrations需纳入定向检查。静态检查不能确认评分器行为。
2. 评分器运行验证：另获授权后在Linux容器核对正确实现、典型错误、-I下同级模块加载、超时/超量输出与进程回收、缺失及传输异常分类、预算和诊断有效性。它不调用Agent，不代表真实Agent结果。需要新增仓库测试、fixtures、mocks或snapshots时须另获授权。
3. 真实Agent评测：另确认目标、范围、重复次数、并发、超时和金额预算，再导入、发布和创建实验。

## 8. 待验证事项与下一轮审阅重点

目前仍缺新数据集、评分器及离线校验器的实现；新加载器、严格类型/别名检查、错误分类、进程回收和资源参数均无运行证据。还缺首批三题在两个真实Agent上的耗时、费用、通过分布和重复稳定性材料。因此本修订仅消除方案歧义，不把可实施判断升级为实现完成或验收通过。

1. 九题是否重复、欠缺代表性或存在业务歧义？哪些规格必须先补齐？
2. Agent公开规范和评分预期是否一致，有没有隐藏要求或未检查要求？
3. 全部100分才通过、同时保留部分分，是否适合版本回归？复合检查分值是否合理？
4. 仅平台级要求input、插件自行判断必要证据是否存在误判风险？
5. HTTP漏交文件的保守处理是否合理，是否必须首批就补完整采集清单？
6. 多文件导入、-I与本地模块加载、文件名保留、隔离、进程回收和诊断保存是否遗漏实现约束？
7. 评分资源参数、检查进程数量和复合检查语义是否一致、可维护？
8. 现有契约、比较和rescore是否支持所述方案，有无需要额外改核心代码之处？
9. 是否可以在不改数据库结构、公共契约和外部Agent的前提下完成首批？新增数据库记录与结构迁移是否已明确区分？

审阅应给出可定位的源码或文档依据，区分已确认事实、推断、待确认问题。按必须修正/建议优化/可接受列出结论，并提出最小修订方案；不要执行实现或评测。
