# 订单多文件题：第二次真实评测

日期：2026-10-16（Asia/Shanghai）。本轮只执行订单题一次，结果为 **unknown，无有效质量评分**。
第8次模型请求返回 HTTP 500（响应体为503/ServiceUnavailableError），缺少usage及模型停止确认；
原键只读恢复查询仍返回unknown。没有重跑，没有将产物记为代码零分，也没有运行78条件评分。
[首轮](coding-regression-real-acceptance-20261016.md)的订单截断失败及chunk/整数CLI通过记录全部保留。

## 授权、隔离和历史关联

先按用户要求完成只读核查，未启动服务、调用模型或写平台记录；核查时本地HEAD及远端main
均为`6d5445bdecda232a13b7f5e198cddbf03625f215`，工作区干净。用户回复“按你的方案来”，
明确授权8192完成token、240秒请求超时、仅订单一次、并发1、无自动重试、独立人民币1元预算，
以及必要服务、新记录和首轮冷态副本。本轮没有使用首轮剩余预算作为授权。

只读阶段Docker Linux引擎不可达；授权后隐藏启动Docker Desktop，Engine为29.8.2。
首轮组件及其他历史容器均保持停止，没有容器使用待复制源卷。新命名空间为
`eyes-coding-order-real-20261016-r2`，API仅绑定宿主127.0.0.1:18088。

首轮PostgreSQL和证据卷以只读挂载冷态复制到本轮新卷；对相对路径、类型/权限、UID/GID及
文件字节SHA-256逐项核对：数据库1449项、证据卷5项一致。副本直接沿用既有0007 schema，
未执行迁移或maintenance。Agent、预算及两个Runner状态使用全新卷，不复制首轮Agent账本。
原始源卷收尾再核对清单一致；全部历史容器的运行状态、启动及停止时间与启动后基线一致。

新实验位于**副本数据库**，`parent_experiment_id`指向副本中保留的首轮实验；
不是跨数据库外键，也没有向原数据库写入本轮记录。副本中的首轮订单Attempt完整详情和首轮
实验汇总在本轮前后相同。首轮原环境、原始材料和失败记录均未覆盖。

| 记录 | UUID |
| --- | --- |
| Project（冷态复制保留） | c586fc3b-e959-4200-b0ce-0c175c31ce79 |
| 首轮Experiment / parent | d8fd124e-6796-45ed-90b0-8c9cbca84679 |
| 首轮订单失败Attempt | 34654a34-da8d-4481-a68e-5b15de9c917c |
| 第二次TargetVersion | 12f05944-ff12-432e-bb7a-d27604c2c1e8 |
| 第二次单题DatasetVersion | 913f11d9-fc05-49af-9d3d-49ba9fb58e09 |
| 冻结ScorerVersion（复制保留） | 20833998-d236-4666-9d2b-67a30665b4dc |
| 第二次Experiment | 9021df4f-2a33-458d-b312-4dbd679b81ae |
| 第二次唯一Attempt | 4e5050a6-623d-4270-83c4-5ee0cd70115d |
| 远端run | 4a0e0810-a7cb-40e2-b011-2e37a21476f2 |
| Manifest v1，partial | bd9981f9-cc9a-4b3b-852a-4eba99d67b20 |

## 实际加载版本和配置差异

| 项 | 本轮核验 |
| --- | --- |
| Eyes源码 | 从6d5445b实际字节制作只读副本，78个Python文件与首轮一致；API实际加载/app/src/eyes |
| Eyes源码映射摘要 | 6765be1d9c3d85d04037cc39c1ce6edd366137dcbc2352c25fa46d8dc515bc6f |
| trae | e6e03825d63ad764b4f2535e6db5cd10dcce1a97，工作区干净；实际加载/live/trae_agent，11文件与首轮一致 |
| trae源码映射摘要 | 9025cf1b1318359acc7ae78c82510555a949cc8f4908a77476e3b69e7f99b167 |
| Agent解释器/依赖 | Python3.14.8；httpx0.28.1/FastAPI0.143.0/Pydantic2.14.0/Uvicorn0.54.0，与首轮一致 |
| 控制解释器 / PostgreSQL | Python3.14.7 / PostgreSQL18.6，与首轮一致 |
| 控制镜像ID | sha256:4775a9362087d827e6131e51be73c0e970aaf88b247d606c9142c892daa2ab82 |
| Agent镜像ID | sha256:0fa7d20782cc27f3ee92f70befca912582b47b5d4d1cb474fe58cf74e13e9407 |
| PostgreSQL镜像ID | sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336 |
| 评分器实际字节摘要 | 072411a84a3074ced8f736d5dc6f871d7404d258944aabbefc8aeb7eab38c5a1，与Runner插件发现及冻结版本implementation_digest相同 |
| 完整评分数据字节摘要 | 1c518bb176522261c3b98598f87d693d6f334a5e992fb695461a7cf0a10439c1，仍为scorer.config.dataset_sha256 |
| 原样订单Case内容摘要 | d229ea07d5fb23fc0a6f14a28be0e1caacba8a4708e7c36369bb14aacf581ec4，与首轮一致 |
| 单题平台数据集内容摘要 | 8083cf00ef233f98217d65d62d1e47ffa5891bf984c9fc55442a9840b691aa74 |

源码映射摘要口径沿用首轮：相对路径→实际字节SHA-256，sort_keys紧凑JSON后SHA-256。
评分器配置、阈值、组权重及78条件没有变化。认证discovery与首轮能力完全一致：并发1、
session_isolation=true、environment_isolation=false、cancellation/resources=false、events/artifacts=true。

| 配置 | 首轮 | 第二次 |
| --- | --- | --- |
| 模型 / thinking / stream | mimo-v2.6-flash / enabled / false | 相同 |
| 每响应完成token上限，含推理 | 4096 | **8192**，AGENT_MAX_OUTPUT_TOKENS，经全部8个model.request事件核对 |
| 单模型请求超时 | 120秒 | **240秒**，AGENT_REQUEST_TIMEOUT_SECONDS，经服务实际Config核对 |
| 任务总超时 / 证据等待 | 480 / 60秒 | 相同 |
| 模型调用 / 工具调用上限 | 24 / 48 | 相同 |
| 工具默认 / 参数允许上限 | 20 / 60秒 | 相同 |
| 并发 / repetitions / attempt_selection | 1 / 1 / first_success | 相同 |
| 数据集范围 | 三题各一次 | **仅原样订单行**，没有chunk/int工作入队 |
| 预算 | 首轮三题共享独立1元账本 | **本轮订单独立1元新账本**，初始calls/spent/pending均0 |
| 运行状态 | 首轮独立环境 | 新控制副本、新Agent和Runner状态、凭据、目标版本及运行时间 |

平台ExperimentCreate没有case筛选参数，因此导入原样订单行形成单题数据集；没有修改公开题目、
初始文件或expectations。评分容器保留完整冻结JSONL，未将其替换为单题文件，也未改评分配置摘要。
预算仍是请求前预留机制，独立预算范围及冷缓存/服务负载均需作为比较背景说明。

保留首轮其他限制：执行/评分全局及项目额度均1，目标额度1，max_preparation_attempts=1；
Agent为非root UID10001、2CPU/2GiB/pids256，执行Runner为1CPU/1GiB/pids128，均init=true。
max_artifacts=100，单产物32MiB，必需代码每文件256KiB。评分配置仍为独立进程、120秒超时，
CPU45秒/AS512MiB/单文件1MiB；候选3秒、双通道各64KiB、每波8个、阶段60秒及10秒预留。
这些评分限制只完成配置/插件核查，本轮没有启动评分Runner或候选评分进程。

## 执行结果、证据及判定边界

执行意图至平台记录结束：2026-10-16 **23:08:30～23:16:14（Asia/Shanghai）**，
464.27秒；包含接入和证据上传开销，不是纯模型耗时，也不是停止已确认的证明。

| 口径 | 本轮结果 |
| --- | --- |
| 计划 / 实际Attempt | 1 / 1，仅订单 |
| 执行成功 / 确认failed / unknown | 0 / 0 / **1** |
| 超时 / 取消 | 0 / 0，不能因为接近480秒而改记超时 |
| 模型请求 / 完整usage结算响应 / 请求错误 | **8 / 7 / 1**，无自动付费重试 |
| 工具调用 / 工具结果事件 | **11 / 11** |
| 有效评分 / 覆盖率 | 0 / 0/1；78条件未运行 |
| 质量pass / fail | 0 / 0；0/0有效评分通过率不可计算，无均分 |
| 评分error / insufficient_evidence / skipped / N/A记录 | 0 / 0 / 0 / 0，根本未创建ScoreRun |
| 实验状态 / 清理 / 证据 | completed_with_unresolved / unknown / partial |

第8次请求的错误码为model_http_error：HTTP状态500，正文error.code为503、
type为ServiceUnavailableError。现有trae在_post HTTP异常路径不结算usage、不清除pending预留；
http_service检测预留未释放后报告model_stop_confirmed=false，协议结果为unknown、
stopped_confirmed=false、completed_at=null。这是上游错误造成的执行结果未知，
不是代码质量fail、评分器错误或已确认执行失败；partial证据状态也没有伪写成某个评分器的
insufficient_evidence结果。没有修改Agent、核心Runner、公共契约或数据库结构。

7个完整响应均为tool_calls，最大完成token为3566，未见length截断；头两个模型响应耗时
分别为131.267和170.734秒，均超过首轮120秒请求超时。可观察到本轮进入了工具执行阶段，
但不能把这一点单独归因于8192上限：请求超时也变化，模型响应不同且最终未成功完成任务。
首轮未采集完整模型IO，本轮capture_model_io仍false；不能推断内部推理分配或声称质量改善、稳定性。

本轮保存49个事件、4个产物、12610字节，Manifest v1为partial。已独立核对：
事件归属及content摘要、Manifest归属及摘要、产物引用在清单内、所有下载字节与平台size/SHA-256一致，
Agent持久任务仅收到与订单input完全相同的prompt/files，没有评分预期或验证材料。
普通评分没有发生，因此不存在ScoreRun绑定或评分引用可以验证；不伪造评分审计通过。

| 真实采集产物 | 字节 | SHA-256 |
| --- | ---: | --- |
| money.py | 920 | ae0a1c742a4752370f150fe6c95cb322296c001977dd04607f62ab0361726b14 |
| order.py | 1553 | 731d8c35a98a1f40d249ef5b9883300d0e6805fa440f80c9d3a264f58286182c |
| main.py | 1230 | 501c75db61f5e1a0e175b06af69aea146b326da7f49c39b16d84ac992852c67b |
| _selfcheck.py | 8907 | 55a36d4d93b6364231d092eeb68f8fe848acf55de75212248e554f6fbbde38d4 |

三个必需文件已与初始骨架不同，但没有执行独立质量评分，不能称为正确实现。
_selfcheck.py是Agent真实生成并采集的额外文件，不是本轮维护者新增的仓库测试，未提交或用作评分依据。
未用旧候选替代产物，也未额外运行产物来绕过unknown状态评分。

## 费用与未确认预留

本轮沿用已核对的[官方国内实时按量价](https://mimo.mi.com/docs/zh-CN/price/pay-as-you-go)：
未缓存输入1元、缓存输入0.02元、输出2元/百万token。
[官方API说明](https://mimo.mi.com/docs/zh-CN/api/chat/openai-api)中的max_completion_tokens
包含推理和可见输出。8192下最大单请求预留0.532480元，比首轮多0.008192元。

本轮账本7次已结算，输入50305 token（缓存38464）、输出9206 token：

```text
((50305 - 38464) × 1 + 38464 × 0.02 + 9206 × 2) / 1000000
= ¥0.03102228
```

第8次请求保留 **pending_rmb=0.184524**；已结算加未确认预留为 **0.21554628元**，
未超独立1元客户端预算。预留不是已确认实际扣费，也不能当作0；最终实际总费用仍未知，
没有供应商账单对账或供应商侧硬封顶证明。unconfirmed_usage_calls字段为0，是因为HTTP错误在
ledger.record之前返回；pending非0仍阻止后续付费请求，不能据该计数字段声称费用全部确认。
没有清空、调整账本或用剩余预算追加执行。

## 原键恢复与收尾状态

执行Runner单次领取后退出0。随后使用同一Runner身份/状态卷、原限定目标凭据和原操作键，
配置recovery_only=true，运行一次`run --once`。该现有模式关闭业务执行及评分槽位，
源码仅GET capabilities和runs/by-key，不调用prepare/execute/cancel/cleanup，也不调用模型。

查询ID为`5c23c6b1-0526-4c6e-a2ca-a1786c8d00d6`；认证查询返回相同Attempt/run、revision3、
unknown及停止未确认，平台追加automatic_agent_http_query来源，applied=false。
只有这一回查询，未继续循环查询、创建恢复执行或人工resolve。查询提交ack已持久化。

收尾核查：只有本轮1个unknown执行工作项保留reserved=true，无queued/claimed工作，
无ScoreRun；Runner pending/rejected/orphaned/corrupt上传均0。
执行状态保留1份work及1份quarantine，原因为workspace retained after unconfirmed or failed cleanup，
属于本次unknown的待恢复隔离状态，未清理或伪报为0；评分状态为空。
Agent进程检查仅见init和服务进程，没有本地工具子进程；这不证明供应商请求已停止。

本轮9个具名容器中，执行Runner、recovery-only Runner、Scheduler、卷初始化及两个复制容器
共6个已停止，退出均0、无OOM。**Agent、API、PostgreSQL这3个组件继续保留运行**，
用于原操作、费用和数据核对；没有连续运行的Runner，不会自动发起新业务或付费请求。
Docker Desktop也保持运行以承载这3个必要组件。未删除任何卷，不能报告“全部正常停止”。

私有配置、凭据、命令日志、源码字节副本、请求/响应、产物、清单、账本和Runner恢复材料位于
Git忽略的`D:\projects\eyes\data\coding-order-real-20261016-r2\`及本轮卷。
归档脚本对API响应包装和unknown隔离状态的假设作了修正，仅重新读取/下载材料，
没有增加业务执行、模型调用、恢复查询或评分。Git仅交付本脱敏记录和入口链接。

未解决项是供应商第8次请求的停止/实际费用确认、原unknown及清理隔离状态、订单质量未评。
后续应基于原键、保留账本和可信供应商事实继续核对；当前不能自动解除额度或重跑。
若以后需要改Agent的供应商异常分类或账本协调，应先提供停止/计费协议证据及最小方案，
本轮没有足够证据批准修改，也没有发现必须修改评分器的问题。
本次不覆盖第二个Agent、其余六题、故障注入或重复稳定性。

交付检查限于文档内容、链接和`git diff --check`；没有重跑已完成的评分器验证，
没有新增维护者测试、fixtures、mocks或snapshots。真实执行、恢复查询、证据核验与文档检查分别记录。
