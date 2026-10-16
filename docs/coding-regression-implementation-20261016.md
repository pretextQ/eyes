# 编码回归扩展实施记录

日期：2026-10-16，Asia/Shanghai。范围为用户本轮授权的三题和必要评分基础设施。
这份记录不代表真实 Agent 验收，不包含数据集导入、评分器发布、实验或比较报告。

## 任务与提交

| 任务 | 实施/检查结果 | 提交及推送 |
| --- | --- | --- |
| 1 基础设施/chunk | 数据集、独立评分插件、离线校验器、文档及Runner绑定示例；18条件；静态通过 | `3b1e9fe`，已推送 |
| 2 整数CLI | 17条件，ASCII词法、严格JSON、错误通道、退出码及导入；静态通过 | `3a58bcf`，已推送 |
| 3 订单多文件 | 78条件，原路径重建、显式加载、函数/真实CLI、验证/取整/不变性/导入；静态通过 | `3e9878a`，已推送 |
| 4 评分器运行验证 | 专项授权后完成独立离线驱动、正确/错误材料、故障矩阵和真实ProcessWorker边界验证；限制见下文 | 静态收尾 `41c9adc` 已推送；运行修复及材料另作本任务提交 |

分支 `codex/coding-regression`，远端 `origin`。开始时工作区只有未跟踪的
`docs/coding-regression-review-proposal.md`；已保留原内容并随任务1纳入版本控制。
草案中的“仅授权更新本文”等为此前授权背景，本轮以用户明确授权为准，未改写草案历史。
旧三题、旧评分器、历史数据、公共契约、数据库结构、核心Runner及外部Agent均未修改。

## 静态检查

Windows宿主机、PowerShell、工作目录 `D:\projects\eyes`：

```powershell
uv run --no-sync python -m integrations.coding.validate
uv run --no-sync ruff check src migrations integrations/coding
uv run --no-sync ruff format --check src migrations integrations/coding
git diff --check
```

三个任务均完成上述相关检查。最终校验结果：三题各100分；条件数18/17/78；
八个候选并行槽位下保守进程预算12/12/40秒。离线校验冻结路径、权重、函数入口、
条件结构、预算和reason长度，不执行候选代码，不证明验收矩阵能检出所有错误。
公开规则及具体验收项已人工对照修订草案；具体验收输入保存在产品JSONL中。

## 已做的本机Linux容器检查

只启动短命、无网络容器；没有启动API、Scheduler、Runner、maintenance或Agent。
没有挂载历史数据、凭据或Docker控制套接字；仓库仅挂载新集成目录和src，均只读。

- Docker Server：29.8.2，linux/amd64。
- 镜像：`eyes-clean-control:20261011`。
- 镜像ID：`sha256:4775a9362087d827e6131e51be73c0e970aaf88b247d606c9142c892daa2ab82`。
- Python：3.14.7（Sep 19 2026, GCC 14.2.0）。
- 内核：Linux 6.18.40.1-microsoft-standard-WSL2，x86_64，Docker Desktop本机后端；
  开发与命令入口仍为Windows/PowerShell，并未转移到WSL开发环境。

PowerShell中的实际配置校验命令：

```powershell
docker run --rm --network none --read-only --tmpfs /tmp:rw,nosuid,nodev,size=64m --pids-limit 256 --memory 2g --cpus 2 --mount 'type=bind,source=D:\projects\eyes\integrations\coding,target=/work/integrations/coding,readonly' --mount 'type=bind,source=D:\projects\eyes\src,target=/work/src,readonly' -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=/work:/work/src -w /work --entrypoint /app/.venv/bin/python eyes-clean-control:20261011 -m integrations.coding.validate
docker run --rm --network none --read-only --tmpfs /tmp:rw,nosuid,nodev,size=64m --pids-limit 256 --memory 2g --cpus 2 --entrypoint /app/.venv/bin/python eyes-clean-control:20261011 -VV
docker run --rm --network none --read-only --entrypoint uname eyes-clean-control:20261011 -srmo
```

均退出0。容器校验输出三题18/17/78条件及配置摘要
`1c518bb176522261c3b98598f87d693d6f334a5e992fb695461a7cf0a10439c1`。
这只验证配置及相关导入在该容器可用，未调用 score，未执行候选，不能称评分器行为验证通过。
该步骤的2 GiB容器上限仅用于离线校验；后续评分器行为验证另见下文。

## 材料核查、补充授权与行为验证

通过 `rg --files` 核查仓库既有评分/验证入口，并只读检查本地data目录。
`rg -l --hidden --no-ignore 'py-chunk-sequence|py-int-cli-errors|py-order-pricing-project' data`
未发现对应新题材料。现有旧三题与历史真实Agent产物不能替代新题的正确/典型错误材料。
没有读取或输出凭据，没有提交私有材料。

完整验证至少需要新增独立离线驱动（使用真实ScoreInput、ScoreContext及临时证据文件，
不连接平台），三题正确/典型错误候选，以及缺失/损坏证据、超时、超量输出、派生子进程
和worker强杀场景的触发材料。首次核查时没有足够的已授权材料，因此暂停行为验证，
先提交静态收尾记录。用户随后明确回复“授权新增这些验证材料并完成任务4”。
之后才创建 `integrations/coding/verification/`，其中候选源码是本轮新生成的公开验证材料，
不含历史Agent产物或私有运行材料。

驱动使用真实ScoreInput、ScoreOutput、ScoreContext和临时字节证据；不替换公共契约，
不运行Agent，不写平台记录。临时评分事件仅写在容器/tmp，在容器退出时删除。
另外直接使用当前源码的 ProcessWorker/worker，仅运行 score/close 评分阶段，
没有启动领取任务的 RunnerService 或调度循环。

实际执行命令（Windows PowerShell，镜像和版本同上）：

```powershell
docker run --rm --init --name eyes-coding-verify-20261016 --network none --read-only --tmpfs /tmp:rw,nosuid,nodev,size=64m --pids-limit 256 --memory 2g --cpus 2 --mount 'type=bind,source=D:\projects\eyes\integrations\coding,target=/work/integrations/coding,readonly' --mount 'type=bind,source=D:\projects\eyes\src,target=/work/src,readonly' -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=/work:/work/src -w /work --entrypoint /app/.venv/bin/python eyes-clean-control:20261011 -m integrations.coding.verification.run
docker run --rm --init --name eyes-coding-worker-20261016 --network none --read-only --tmpfs /tmp:rw,nosuid,nodev,size=64m --pids-limit 256 --memory 2g --cpus 2 --mount 'type=bind,source=D:\projects\eyes\integrations\coding,target=/work/integrations/coding,readonly' --mount 'type=bind,source=D:\projects\eyes\src,target=/work/src,readonly' --mount 'type=bind,source=D:\projects\eyes\src,target=/app/src,readonly' -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=/work:/work/src -w /work --entrypoint /app/.venv/bin/python eyes-clean-control:20261011 -m integrations.coding.verification.worker
```

最后完整运行均退出0；不是只运行静态检查。最终每个完成评分的reason都验证了：
检查ID逐项对应、无遗漏/重复、所有条件有pass/fail、组得分之和等于value、reason合法JSON
且不超过5000字符、引用全部属于当前授权清单。

| 场景 | 实际结果 |
| --- | --- |
| 三题正确实现，含多文件函数/真实CLI/三模块导入 | 均 completed/pass，100分；直接调用约1.1/1.0/4.3秒 |
| chunk允许bool长度/修改输入/导入打印空白 | 分别95/40/85分，completed/fail |
| chunk函数调用打印少量输出 | 100分，符合公开规则 |
| int接受Unicode数字/错误写stdout/JSON布尔count | 分别60/60/50分 |
| order向下取整/JSON不拒绝重复键 | 分别60/96分 |
| 语法错误 | completed/fail，0分 |
| 缺文件、歧义文件、过期证据、无可信来源的missing事件 | insufficient_evidence，无value/verdict |
| 本地下载文件缺失、完整性损坏、配置摘要错误 | error，无value/verdict，未假装代码质量失败 |
| 阶段预算已耗尽、运行部分条件后预算不足 | error，无分数；not_run保留 |
| 单候选超时、stdout和stderr分别超过64 KiB | 对应条件fail，原因timeout/output_limit |
| 候选正常退出、抛异常、超时、输出超限，均带派生子进程 | 各路径均确认候选及子进程从/proc消失 |
| 78个订单条件全部超时 | 完成78项诊断，0分，约32秒，低于40秒保守进程预算/60秒阶段上限 |
| 每候选软资源参数 | 实际读取CPU45秒、AS536870912字节、FSIZE1048576字节，符合配置 |
| 真实ProcessWorker，CPU45秒/AS512 MiB/FSIZE1 MiB | 三题100分；约1.923/1.888/5.356秒 |
| 插件宿主进程SIGKILL | 独立监督进程仍回收候选及后代 |
| 真实评分worker进程组SIGKILL | 确认22个已观测监督/候选/后代PID全部从/proc消失 |

这些是固定环境中的定向验证，不是吞吐基准或长时间稳定性结论。

## 运行发现与修复

1. 第一轮直接验证退出1：正常候选退出后，后代持有管道使原逻辑误判timeout。
   修复为检测组长退出即杀候选进程组，再有界排空管道；正常/异常/超时/超量输出及后代
   回收矩阵均已复验。第一轮失败没有改写为通过。
2. 首次真实worker验证退出1：线程池版本在512 MiB worker中返回
   `infrastructure:RuntimeError`，条件均未运行。移除插件额外线程池，改为每波最多8个监督
   进程，保持并行及预算；相同worker资源配置下三题和强杀路径复验通过。
   未采集native分配轨迹，因此不把具体线程栈/libc arena成因写成已确认事实。
3. 静态收尾已修正函数输出隐含限制和导入空白误判；补充运行中，函数打印仍100分、
   导入打印空行85分，均符合预期。

## 未覆盖边界

Runner下载前置错误的真实HTTP传输、410响应及重试路径未运行验证；这里只验证插件收到
本地缺失/损坏证据后的分类，没有据此宣称核心Runner的HTTP分类已验收。
没有启动领取任务的Runner、Scheduler或真实Agent，也没有导入、发布或创建平台记录。
未验证真实模型费用、并发Agent容量、任意恶意候选另建会话、进程树总资源额度或长期负载。
CPU/AS/FSIZE的限额值与配置已实测，未逐一施加CPU/内存/磁盘耗尽压力；回收已在上述有限
故障场景检查，不保证所有内核/部署故障均已覆盖。未发布评分器，真实Agent验收仍待单独授权。

实现限制见[编码回归说明](../integrations/coding/README.md)。100分仅表示冻结检查通过；
缺失来源无法绑定时返回证据不足；独立进程不是安全沙箱；单进程资源限制不是进程树合计。
真实Agent评测留待后续授权，届时明确目标版本、范围、重复次数、并发、超时及费用预算。

收尾静态复核修正：函数调用输出不属于公开禁令，改用末尾结果帧判定函数结果；仍受64 KiB限额约束。独立导入和CLI通道规则继续严格检查。修正后Ruff及离线矩阵校验通过，未将此修正描述为运行验证发现。

另将导入检查改为精确检查器输出帧比较，防止把候选导入时打印的空白误认为静默。
静态收尾时尚无运行证据；补充授权后的运行结果已在上表列出。
