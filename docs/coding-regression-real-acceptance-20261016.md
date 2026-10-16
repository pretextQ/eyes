# 首批编码回归：trae 单次真实评测记录

日期：2026-10-16（Asia/Shanghai）。结论：本轮已按授权执行三题各一次；
**chunk、整数CLI执行成功且独立评分通过，订单题执行失败，没有有效质量评分**。
不是新三题全部验收通过，不证明稳定性、第二个Agent适配或版本改善/退化。

## 授权和范围

先完成[交付复核和评测准备](coding-regression-preflight-20261016.md)，提交 `4ceb1fe`。
用户回复“进入”，授权按该冻结方案执行：一个trae目标、三题各一次、并发1、
480秒/题、三题共享人民币1元预算；不扩展目标、重试或重复次数。

全部平台记录位于新命名空间 `eyes-coding-real-20261016`、新PostgreSQL/证据/Agent/预算/
Runner状态卷；新库仅应用既有迁移到0007，未新增或修改schema、公共契约、核心Runner或外部Agent。
没有启动maintenance、修改旧实验/评分/报告或清理历史环境。本轮没有新增/修改仓库测试、
fixtures、mocks、snapshots，也没有使用此前验证候选代替真实Agent产物。

## 实际加载版本

| 项 | 实际值与核查 |
| --- | --- |
| Eyes执行源码 | 从4ceb1fea647a31cecce561712e2f7baf63047f35制作原始字节只读快照；执行代码与b4127d9一致；API实际加载/app/src/eyes，78个Python文件逐项匹配快照 |
| Eyes源码映射摘要 | 6765be1d9c3d85d04037cc39c1ce6edd366137dcbc2352c25fa46d8dc515bc6f；src相对路径→字节SHA-256映射，sort_keys紧凑JSON后SHA-256 |
| trae | e6e03825d63ad764b4f2535e6db5cd10dcce1a97，实际加载/live/trae_agent；11个Python文件逐项匹配，映射摘要9025cf1b1318359acc7ae78c82510555a949cc8f4908a77476e3b69e7f99b167 |
| 模型请求配置 | mimo-v2.6-flash；https://api.xiaomimimo.com/v1；thinking enabled；非流式；模型别名不保证供应商内部权重不变 |
| Agent环境 | Linux、Python3.14.8，httpx0.28.1/FastAPI0.143.0/Pydantic2.14.0/Uvicorn0.54.0；非root UID10001 |
| 控制/评分环境 | 本机Docker Desktop Linux容器，Python3.14.7；开发和操作入口仍为Windows/PowerShell |
| 控制/评分镜像ID | sha256:4775a9362087d827e6131e51be73c0e970aaf88b247d606c9142c892daa2ab82 |
| Agent镜像ID | sha256:0fa7d20782cc27f3ee92f70befca912582b47b5d4d1cb474fe58cf74e13e9407 |
| PostgreSQL镜像ID | sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336，18.6 |
| 评分插件 | coding_regression，实际字节摘要072411a84a3074ced8f736d5dc6f871d7404d258944aabbefc8aeb7eab38c5a1，与发布implementation_digest相同 |
| 数据集实际字节摘要 | 1c518bb176522261c3b98598f87d693d6f334a5e992fb695461a7cf0a10439c1，与评分config.dataset_sha256相同 |
| 平台数据集内容摘要 | 06c6e79a22a7cb626cefb66d0b62df811449ec633bf7c5cf5360bc10694ae839，导入响应与准备阶段计算值一致 |

只读复制保留Windows实际字节，未把Git LF blob摘要混作发布摘要。Agent容器不挂载coding评分/
验证目录，只加载业务Agent及必要Eyes协议源码。认证能力发现的Agent版本与实际源副本一致：
并发1、session_isolation=true、environment_isolation=false、cancellation/resources=false、
events/artifacts=true；统一HTTP适配器提供幂等和原操作核对。

## 新记录和执行配置

| 记录 | UUID |
| --- | --- |
| Project | c586fc3b-e959-4200-b0ce-0c175c31ce79 |
| TargetVersion | 4c2ab602-c6c2-4407-85a8-d0a23a895d0a |
| DatasetVersion | 7197897c-791f-47ec-a49a-800f8cf24c1c |
| ScorerVersion | 20833998-d236-4666-9d2b-67a30665b4dc |
| Experiment | d8fd124e-6796-45ed-90b0-8c9cbca84679 |

实验repetitions=1、concurrency=1、timeout_seconds=480、evidence_wait_seconds=60、
attempt_selection=first_success。评分0～100、higher、threshold=100、mean、required_evidence=[input]，
评分超时120秒。平台全局、项目、目标执行额度均1，评分额度1；服务端实际核查
max_preparation_attempts=1。未修改旧评分器或发布替换版本，未使用retry-score/rescore。

Agent每题模型调用上限24、工具调用48、单响应max_completion_tokens=4096（含思考），
模型请求120秒；工具默认20秒、参数可指定至既有60秒上限。Agent容器2CPU/2GiB/pids256；
执行Runner为1CPU/1GiB/pids128；评分Runner为2CPU/2GiB/pids256，均启用init。
评分worker及各候选软限CPU45秒/AS512MiB/单文件1MiB，不是进程树合计。
候选3秒、stdout/stderr各64KiB；每波最多8个、阶段60秒并受deadline和10秒预留约束。

使用新execute-only/score-only凭据、Runner身份及状态卷，逐题单次领取：

```text
eyes-runner --config /runner.toml run --once
```

每个execute Runner只有1个执行槽、0评分槽，每个score Runner相反。下一题仅在前题
成功执行、评分完成、产物和费用核对后启动。本轮共启动3个单次execute Runner、2个单次score Runner。

## 实际结果

业务执行时间为2026-10-16约17:57至18:03（Asia/Shanghai）。下表用时为Attempt的
execution_intent_at至平台finished_at，包含接入和结果上传开销，不是纯模型耗时或性能基准。

| 用例 | 执行 | 普通独立评分 | 条件 | 模型/工具调用 | 用时 | usage计价费用（元，6位小数） |
| --- | --- | --- | --- | --- | --- | --- |
| py-chunk-sequence | succeeded | completed/pass，100 | 18/18 | 10 / 12 | 94.91秒 | 0.014514 |
| py-int-cli-errors | succeeded | completed/pass，100 | 17/17 | 11 / 13 | 95.86秒 | 0.012376 |
| py-order-pricing-project | failed：output_truncated | 未创建；无value/verdict | 未运行78条件 | 1 / 0 | 79.87秒 | 0.008655 |

订单题首个模型响应用满4096完成token，Agent按既有规则返回output_truncated，且远端
stopped_confirmed=true。尚未发生工具调用，采集到的money.py/order.py/main.py均与初始文件字节相同。
没有把初始骨架送去普通质量评分，也没有把执行失败填成代码零分。未采集完整模型IO，
不能断言是何种思考/可见输出分配导致截断；没有增加输出上限或用剩余预算重跑。

| 汇总口径 | 结果 |
| --- | --- |
| 计划 / 实际Attempt | 3 / 3（各题恰一次） |
| 执行成功 | 2/3 |
| 执行失败 | 1；超时0、取消0、unknown0 |
| 有效评分 / 覆盖率 | 2 / 2/3 |
| 质量pass / fail | 2 / 0，有效评分通过率2/2 |
| 评分error / insufficient_evidence / skipped / N/A | 0 / 0 / 0 / 0 |
| 未获得有效评分 | 1，已确认为订单执行失败，不是未知执行 |
| 有效评分均分 | 100，必须与2/3覆盖率一起阅读 |

实验状态completed只表示本次调度结束，不等于三题质量全部通过。执行失败和没有评分的题目
仍保留在计划分母，不以2/2有效评分通过率替代全计划2/3通过覆盖情况。

## 证据与费用复核

chunk和int的ScoreRun分别绑定其唯一成功Attempt、本次新ScorerVersion和封存Manifest v1。
已经逐项核对：manifest.attempt_id、score.attempt_id/scorer_id/manifest_id、内容摘要、
引用属于冻结清单、必需代码名字唯一且被引用；reason的检查ID完整、无未执行条件，整数组分之和等于value。
订单Attempt没有ScoreRun，只有执行结果与封存证据，不伪造评分绑定。

三次均sealed、声明丢弃事件0、清理succeeded、远端停止已确认。总计117个已存事件、5份真实产物、
2686字节，全部经只读凭据从平台下载并与对应Attempt的Artifact元数据size/SHA-256逐项匹配。
5份包括两份完成代码及订单的三份未修改初始代码；不能把“采集到5文件”解读为5份均已实现。
Agent持久协议task逐项核对仅含公开prompt/files，等于用例input；没有收到expectations、评分配置或验证候选。
采集范围仍只是已声明模型/工具/产物边界，不宣称内部思考、完整全文件清单或任意环境隔离。

三题共享的新预算账本上限1元，没有复用/清空旧账本；所有模型请求经既有客户端请求前预留，
没有自动付费重试。最终账本：22次已结算模型调用，输入74897 token（缓存64000）、
输出11684 token；pending_rmb=0、unconfirmed_usage_calls=0。
按本轮冻结的[官方实时按量价](https://mimo.mi.com/docs/zh-CN/price/pay-as-you-go)计算：

```text
((74897 - 64000) × 1 + 64000 × 0.02 + 11684 × 2) / 1000000
= ¥0.035545
```

这是供应商usage按已核对价率结算的账本费用，没有完成供应商账户账单对账；不是供应商侧
硬封顶证明。最终无未确认费用，未超1元授权预算；未用剩余额度追加任务。

## 原始材料和服务收尾

私有操作脚本、实际命令stdout/stderr、配置、凭据、字节源快照、请求/响应、产物、
Attempt/ScoreRun/Manifest详情、费用账本及Runner状态均位于Git忽略的
`D:\projects\eyes\data\coding-real-20261016\`及对应新卷。本次Git仅提交本脱敏汇总和入口链接，
不提交原始运行材料或密钥。操作日志中的凭据字段做了脱敏，私有env/令牌文件按运行需要单独保留。

实际阶段：独立服务初始化及版本核验→发布新记录→创建唯一实验→execute-1/score-1并核验→
execute-2/score-2并核验→execute-3确认执行失败→证据/费用归档→正常停止。私有归档脚本中
对不存在的score-3容器和Attempt.started_at字段的假设已改为实际记录结构；没有因此重跑业务、
创建新Attempt或新ScoreRun。这些操作脚本调整不属于评分器或Agent源码修复。

停止前确认本项目没有queued/claimed/unknown工作、没有reserved额度、没有证据等待，
Runner pending/rejected/orphaned/corrupt/quarantine均0。score状态目录保留2份评分工作记录，
属于既有保留评分轨迹行为，不是未完成工作。

本轮11个容器（含迁移、卷初始化、单次Runner和服务）全部停止，没有删除卷或恢复材料：
Agent/API经docker stop接收SIGTERM，退出143，日志均确认Application shutdown complete，
无OOM；其他容器退出0。退出143没有伪写成0，也不是SIGKILL退出137。
Agent状态在停止前和停止后均保留副本，预算和Runner状态保留在原新卷。
既有 `eyes-capacity-web-20261014-api` 与对应pg继续运行，未启动或更改其他历史组件。

本轮未发现需修复评分器的问题。订单剩余项是执行输出截断；若以后要提高输出上限并再测，
需另行确认参数、范围和费用，使用新记录，不能覆盖本次失败。
HTTP传输/410重试故障注入、资源耗尽、长期负载、第二个Agent及重复稳定性仍未覆盖。

交付检查：`git diff --check`和本次文档本地链接核查通过；此前交付复核的离线校验/Ruff通过。
本轮文档修改不触发重复完整评分器故障验证；静态检查、已有评分器验证和本次真实Agent结果分开记录。
