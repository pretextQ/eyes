# 编码回归扩展实施记录

日期：2026-10-16，Asia/Shanghai。范围为用户本轮授权的三题和必要评分基础设施。
这份记录不代表真实 Agent 验收，不包含数据集导入、评分器发布、实验或比较报告。

## 任务与提交

| 任务 | 实施/检查结果 | 提交及推送 |
| --- | --- | --- |
| 1 基础设施/chunk | 数据集、独立评分插件、离线校验器、文档及Runner绑定示例；18条件；静态通过 | `3b1e9fe`，已推送 |
| 2 整数CLI | 17条件，ASCII词法、严格JSON、错误通道、退出码及导入；静态通过 | `3a58bcf`，已推送 |
| 3 订单多文件 | 78条件，原路径重建、显式加载、函数/真实CLI、验证/取整/不变性/导入；静态通过 | `3e9878a`，已推送 |
| 4 评分器运行验证 | 材料核查及容器内离线配置校验已做；静态修正函数调用输出判定；行为验证未完成，等待验证材料专项授权 | 本记录属于收尾修改，提交后记录在Git历史 |

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
运行时2 GiB容器上限仅用于离线校验；不作为八个候选槽位的已验证容量配置。

## 材料核查与未覆盖项

通过 `rg --files` 核查仓库既有评分/验证入口，并只读检查本地data目录。
`rg -l --hidden --no-ignore 'py-chunk-sequence|py-int-cli-errors|py-order-pricing-project' data`
未发现对应新题材料。现有旧三题与历史真实Agent产物不能替代新题的正确/典型错误材料。
没有读取或输出凭据，没有提交私有材料。

完整验证至少需要新增独立离线驱动（使用真实ScoreInput、ScoreContext及临时证据文件，
不连接平台），三题正确/典型错误候选，以及缺失/损坏证据、超时、超量输出、派生子进程
和worker强杀场景的触发材料。这些属于本轮明确禁止自行新增的验证材料，已请求专项授权。
授权前不新增脚手架、fixtures、mocks、snapshots或内联自测。

以下全部仍为未完成：正确实现满分、典型错误扣分、缺失/传输故障分类的实际路径、
多文件导入及CLI、超时、stdout/stderr超量、正常/异常/强杀后的进程回收、实际资源预算、
完整诊断输出。Runner下载前置错误的真实传输验证还需单独隔离的下载环境，不能通过
插件内损坏文件检查声称已验证核心Runner的HTTP分类。

实现限制见[编码回归说明](../integrations/coding/README.md)。100分仅表示冻结检查通过；
缺失来源无法绑定时返回证据不足；独立进程不是安全沙箱；单进程资源限制不是进程树合计。
真实Agent评测留待后续授权，届时明确目标版本、范围、重复次数、并发、超时及费用预算。

收尾静态复核修正：函数调用输出不属于公开禁令，改用末尾结果帧判定函数结果；仍受64 KiB限额约束。独立导入和CLI通道规则继续严格检查。修正后Ruff及离线矩阵校验通过，未将此修正描述为运行验证发现。

另将导入检查改为精确检查器输出帧比较，防止把候选导入时打印的空白误认为静默。此项同样仅经静态检查，运行验证未完成。
