# MewCode / trae 主动接入、并发与恢复验收

日期：2026-10-12（Asia/Shanghai）。结论：本轮双目标真实闭环、实际并发、定向凭据范围、成员准备失败隔离、批次取消、trae 原操作恢复及正常停止/重启通过下述范围；**M1/M2 不宣布整体通过**。取消/资源正向能力及安全沙箱没有实现。双 Agent 结果不作为同 Agent 版本改善/退化。

## 实际身份和环境

先读 Eyes `AGENT.md`、README/architecture、PLAN、统一协议/Schema/契约、agent-http-runtime、multi-agent-batches、Runner 可靠性及最新按需/观测验收；trae DEVELOPMENT/ACCEPTANCE/IMPLEMENTATION/OBSERVATION；MewCode MEWCODE/README 与 Eyes 的真实 bridge/HTTP 接入说明。目录名不作为独立 Agent 依据。

| 项 | 实际值 |
| --- | --- |
| Eyes 执行源码 | `4debab95b8a6b34f884df49e563d70982ff8dce8`；冻结 src 副本用于 API/Scheduler/Runner/协议服务 |
| MewCode | `D:\projects\MewCode`，`3f104082b6c5ca53efe273630bf08f67f1fc3ff5`；158 个实际加载 Python 文件逐项匹配该 checkout |
| trae | `D:\woker\trae`，初始 `27aa319fdd19b03df2fc7bddf0b3ab7152ad1458`；11 个实际加载 Python 文件逐项匹配；接入修正版本 `357d2ecdd1652c4ec0adb5b8e1685b01fdf51053` 另行发布、真实执行 |
| 实际请求模型 | MewCode `deepseek-flash`（官方当前映射 V4.1-Flash，别名不等于冻结权重）；trae `mimo-v2.6-flash`、thinking enabled，`https://api.xiaomimimo.com/v1` |
| trae 运行环境 | Linux CPython 3.14.8、非 root UID 10001；httpx 0.28.1、FastAPI 0.143.0、Pydantic 2.14.0、Starlette 1.7.0、Uvicorn 0.54.0，与 trae 当前锁定条目相符 |
| MewCode 运行环境 | Linux CPython 3.14.7、UID 10001；OpenAI 2.34.0、Anthropic 0.98.1、FastAPI 0.142.2、Pydantic 2.13.5；组合依赖检查通过，不宣称逐项等于 MewCode 自身锁文件 |
| 原样输入和评分 | `integrations/deta/coding-smoke.jsonl` 字节 SHA-256 `9e868ae0c53f1e2f88d6114b5c76e591647ecd78ef6b6d3882cbaf8b49771e4b`；`scorer.py` SHA-256 `3e72cfd6a721cddd420f9d850cf79366545e886ec59b7377424c01fb0737d826` |

源码摘要方法：实际包目录相对 Python 文件名→SHA-256 映射，JSON sort_keys 后摘要。trae 初版 `9101321fc86644260750449d72a3d7fa38bae2261cf6a3963694fecdbac19976`；MewCode `dab856d15e0a8f344f221dc1decfc507c8f7ef66b680af1326fe13bbd90a7c45`。不与使用其他排序/路径方法的历史摘要直接比较。

trae 自己的 `loop.py` 实例化消息列表、ModelClient、RunRuntime 和 Workspace；工具为 list_files/read_file/write_file/replace_text/run_python。没有导入 MewCode 业务代码或执行循环；仅复用 Eyes 持久化 HTTP 外壳及契约。输入为 prompt/files，已有三任务兼容，不新增必填字段，不向 Agent 传 expectations、评分配置或平台凭据。事件是实际 task/model/tool/artifact 边界，产物来自工作目录真实字节。没有新建 Agent 或强制 Python 接入。

## 独立部署、预算和发布

Docker 最初 Linux 引擎不可达；启动 Desktop 后原容器全部停止，没有启动或写入任务二环境。新命名空间 `eyes-dual-20261012` 使用 PostgreSQL 18.6（55450）、API 18072、Agent 19073/19074/19075，新数据库、证据/Agent/Runner/预算卷，迁移至 0005。项目 `2fb02d3f-a313-41de-a973-423d8e743079`。Agent、管理、逐目标 execute、score 凭据分别生成；Runner 各有独立 state_dir/卷。

trae 初版目标 `15caec85-aa4d-40e3-bc92-3f569967e413`；修正版本 `8fad5a85-fcc8-4527-ac4d-e899c248cac0`；MewCode `95d4d3cb-d76f-4e3a-8321-03ac9e5a1790`。能力发现冻结后发布，旧目标/历史保留。Agent URL 保持认证 loopback HTTP，Runner 共享对应 Agent 网络命名空间；控制 API 在私有 Docker 网络。首次尝试用服务名 HTTP origin 被协议拒绝，修正部署，没有放宽 HTTPS 约束。

用户本轮明确总预算 ¥1；MewCode/trae 各 ¥0.50。trae 使用已有请求前持久预留；修正版本分配上限扣除初版已花 ¥0.01419676，不重置预算。MewCode 前置本轮私有费用网关：复用预算记账组件，按原请求字节及完整 8192 输出上限预留，限定原模型和文本请求，原样转发 SSE 字节；完整 usage 才结算，异常保留预留并拒绝后续上游调用，不修改 MewCode 或输出。该网关是本轮操作工具，不宣称 Eyes 已有通用预算产品能力。

计价取当前官方 [MiMo 标准价](https://mimo.mi.com/docs/pricing)及 [DeepSeek 高峰人民币价](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)，不依赖优惠。预留使用每序列化 UTF-8 字节 4 token 加 4096 framing token，属于保守文本估算，依赖供应商遵守输出上限与计价，不能冒充供应商金额硬限额。

最终三个付费账本：trae 初版 16 次/¥0.01419676，修正版本 24 次/¥0.01618828，MewCode 26 次/¥0.04649608；合计 **66 次、¥0.07688112**（DeepSeek 按保守高峰计价）。未确认 usage/预留均为 0。断网故障容器没有外部网络，0 次供应商调用，不算新付费预算。

## 闭环与真实并发

首批次 `b2268f37-8d61-49f4-84fa-db48f1c68f87`，trae 实验 `12a6667e-bdf1-47fe-8caf-82b488ef4f44`、MewCode `24aeee4a-23c6-4438-84bc-9060c3f7b58a`：各执行 succeeded 3/3，独立冻结评分器 completed/pass 3/3、12/12 检查；均 sealed、清理 succeeded。修正版本另完成原三任务 3/3 执行/评分、12/12 检查。九个正常闭环 Attempt 的 **15 份产物**通过 API 下载，大小与 SHA-256 全匹配；各评分绑定所属清单和引用，评分进程独立于执行 Agent。

项目/全局 execution=2、score=1；每目标 concurrency=1，每 execute Runner 槽 1，score-only Runner 槽 1。两目标均 session_isolation=true、environment_isolation=false，未提高单体并发。独立目录、消息历史、工具运行状态、凭据和状态卷已核对；不是针对任意恶意 Python 的 OS 安全沙箱。

实际 target_trace 事件（北京时间）：trae fix-mean `10:58:22.263015–10:58:46.857143`；MewCode fix-mean 的真实 mewcode.run `10:58:22.530640–10:58:28.907588`，**重叠 6.376948 秒**。同一 trae 区间还分别与 MewCode 后两任务重叠 3.859175/6.149320 秒。起止来自 Agent 执行边界，不使用排队、页面状态、Eyes 上传时间或采样数量推断并发。已证明实际并发 2；没有容量压测或推广吞吐结论。

## 凭据、失败、取消与恢复

20 个具名实际权限请求：各 execute 凭据下载本目标产物 200、另一目标 403，领取 score 403、读取管理实验 403；Runner 或另一 Agent 凭据访问 Agent 401；read 读取批次 200、取消 403。两个 Agent 的 cancel/resource 端点均 422 unsupported_capability。取消/资源能力继续 false，不声称正向停止确认或资源字节上传通过。跨项目/过期/撤销等通用范围沿用[既有真实权限验收](clean-deployment-permissions-20261011.md)，本轮未穷尽重做。

真实成员准备失败批次：trae Runner 无对应 Agent loopback 服务时三个 Attempt failed（ConnectError，未启动业务），MewCode 三项 succeeded/独立 pass，所有成员额度最终归零。首个故障部署把 Runner 放在已停止 Agent 网络命名空间，导致无法访问控制端，只得到排队，不算失败验收；随后使用独立可达控制端、Agent loopback 不可达的 Runner，才得到上述真实准备失败。

恢复/取消批次中强杀整个 trae execute Runner，Agent 保持独立运行；取消整个批次后各成员两项排队任务 cancelled，活动任务不据此认定远端停止。trae 原 Attempt `5b9be450-8001-465c-a702-e3cf3b76de3e` 从 cancel_requested→unknown，批次进度保留 reserved=1；原远端 run `c8ebe3da-ca78-4579-a406-8e8bab0531e3`。新限定 Runner 仅通过原幂等键查询，找到 succeeded/stopped_confirmed 的同一运行；原 Attempt 转 succeeded，reserved=0，无新业务 Attempt。持久 Resolution 中 applied=true 观察只有一次；随后两次原查询结果提交均 200/duplicate=true。旧 Runner 恢复仅补传三个旧事件（200），没有新执行。MewCode 活动取消同样经原操作查询保留正常成功。各成员最终 1 succeeded+2 cancelled，批次 completed；**该故障/取消批次未产生有效通过评分，证据/评分缺口保留**，不能等同首批正常闭环。

原结果 outbox 补传、迟到提交拒绝/晚到事实、查询竞争、退避重启及终态只释放一次的通用 Eyes 证据沿用[Runner 可靠性验收](runner-reliability-20261011.md)：whole-positive、confirmed-final、late-query-repeated-responses 和 unknown/reserved 记录适用于同一 agent_http 恢复路径。不把旧材料算成本轮 trae 新注入；本轮新补原 run 查询、重复核对、旧事件补传及下述 Agent 特有缺陷。

独立断网 trae 原循环实际复现旧接入把未确认模型请求返回 failed/stopped_confirmed=true。修正 `357d2ec` 后返回 unknown、stopped_confirmed=false、completed_at=null、partial；保留预算预留和工作目录。原键重放保持同一 run，服务重启不重跑，ledger calls=0，新提交 429 保留占额。预算耗尽与未知副作用不混为“已停止”。工具清理仍为 best-effort，任意子进程逃逸/供应商远端取消没有验收。

## 正常停止、重启和剩余条件

按需启动、真实使用、正常停止、重启读取、再次停止完成。正常服务停止全部退出 0；故障强杀 Runner 137 是预期注入、单独保留。停止前/重启后批次、固定实验结果、三个 Agent 服务全部原运行快照和 15 份产物摘要一致，三个付费账本一致；结束时本轮容器运行数 0。卷、故障现场与历史保留，没有删除 unknown 或清空旧数据。

所有原始请求/响应、实际源码/依赖、区间、字节、Runner journal、预算和前后状态在 Git 忽略的 `data/dual-agent-20261012/`，不提交凭据或私有运行数据。未新增/修改测试、用例、fixtures、mocks，未改外部 Agent 业务输出，未做 24 小时实验。

M1：第二个真实 Agent 的主动 HTTP 闭环通过本轮范围；新环境 Python/另一开发者或宿主机复现仍保留原条件。M2：双目标并发和本页定向故障通过；取消/资源正向、完整故障组合、未知结果后的完整证据/评分补齐、任意工具子进程停止保障及更强环境隔离仍未覆盖。M3 改善/退化缺口保持；M4 不因本轮按需周期升级为全面发布通过。
