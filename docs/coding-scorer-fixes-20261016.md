# 编码评分器独立审查修复记录

2026-10-16（Asia/Shanghai）。基线 `5eb3f13`，分支 `main`，开始时工作区干净。
本轮只修改编码评分器、直接相关的verification材料与文档；保留既有
[实施记录](coding-regression-implementation-20261016.md)及真实评测结论。

## 独立源码核查与修复

已阅读AGENT.md、README.md、docs/architecture.md、integrations/coding/README.md，
以及scorer、既有验证驱动、候选材料和worker摘要实现。

两项静态审查结论均成立：原supervise以selector中是否还存在输出管道决定循环是否继续，
双EOF后finally直接killpg，尚未退出的主进程会被杀死；原候选输出解析只捕获ValueError /
UnicodeError，JSON深度触发的RecursionError会令监督进程失败，由collect_condition归error。
这是异常覆盖缺口的源码核查结论。本机Python 3.14.7默认C解码器实际接受2000层乃至
30000层数组，未动态复现默认部署下的RecursionError；标准库递归Python解码器在2000层
确实触发该错误。本轮没有运行修复前评分器，不声称完成修复前动态复现。

修复后每轮独立poll主进程；只有主进程已退出且两管道均EOF才正常结束。
双EOF但主进程仍在运行时继续监听父控制管道、等待原monotonic截止时间，未重置3秒预算。
poll取得的真实returncode单独保存，再杀死进程组残留后代并有界回收。
输出限额、组长退出后清理持管道后代、父控制EOF清理及subreaper均保留。
超时仍是条件fail/timeout；wait超时或后代回收无法确认仍向上传播为评分error。

新增candidate_json仅将strict_json调用抛出的RecursionError转换为已有质量失败路径使用的
ValueError，用于候选CLI JSON与末尾函数结果帧。未扩大supervise的异常捕获范围；
数据集、可信监督摘要及equal等检查器逻辑不使用该转换。
CLI先验证退出码/错误通道会将passed设为真，解析异常分支必须显式重置为False；
否则即使捕获深度错误也会误通过。此项直接相关修复同样覆盖普通JSON语法错误。

## 实际运行环境与命令

Windows宿主机，PowerShell，`D:\projects\eyes`；本机Docker Desktop Linux容器。
Docker Server 29.8.2 linux/amd64，镜像 `eyes-clean-control:20261011`，镜像ID
`sha256:4775a9362087d827e6131e51be73c0e970aaf88b247d606c9142c892daa2ab82`。
Python 3.14.7 / GCC 14.2.0；Linux 6.18.40.1-microsoft-standard-WSL2 x86_64。
没有连接历史环境；没有Agent/模型调用、API/数据库访问、导入、发布、实验或重评分。
没有操作订单unknown、费用、历史卷或恢复材料。

实际通过以下公共参数分别启动三个短命容器（容器可并行，临时目录互不共享）：

```powershell
$verifyArgs = @(
  'run', '--rm', '--init', '--network', 'none', '--read-only',
  '--tmpfs', '/tmp:rw,nosuid,nodev,size=64m', '--pids-limit', '256',
  '--memory', '2g', '--cpus', '2',
  '--mount', 'type=bind,source=D:\projects\eyes\integrations\coding,target=/work/integrations/coding,readonly',
  '--mount', 'type=bind,source=D:\projects\eyes\src,target=/work/src,readonly',
  '--mount', 'type=bind,source=D:\projects\eyes\src,target=/app/src,readonly',
  '-e', 'PYTHONDONTWRITEBYTECODE=1', '-e', 'PYTHONPATH=/work:/work/src',
  '-w', '/work', '--entrypoint', '/app/.venv/bin/python', 'eyes-clean-control:20261011', '-m'
)
docker @verifyArgs integrations.coding.verification.regressions
docker @verifyArgs integrations.coding.verification.run
docker @verifyArgs integrations.coding.verification.worker
```

三入口均退出0，末尾分别输出regressions/verification/actual_worker_verification complete。
只挂载本轮代码及src为只读；无凭据、历史卷、Docker套接字。Docker init回收孤立监督进程。

| 本轮运行场景 | 实际结果 |
| --- | --- |
| CLI正确JSON，关闭双通道后再等待0.35秒，以0或2退出 | 均pass/ok，约0.668/0.618秒，保留真实退出码 |
| 同场景退出7或SIGTERM | 均fail/behavior，均约0.619秒 |
| 双EOF后持续30秒 | fail/timeout，3.080秒，PID已消失 |
| 先运行1.8秒再双EOF，再计划运行1.8秒 | fail/timeout，3.130秒，未延长原截止时间 |
| 主进程关闭通道后延迟退出，后代仍持有管道 | pass/ok，0.518秒，主进程及后代PID均消失 |
| 双EOF后父控制管道关闭 | parent_closed，监督进程退出0，候选已回收 |
| CLI输出2000层嵌套JSON，4002字节（含换行） | completed/fail，50分；17条件全部pass/fail，其他条件有pass |
| 候选伪造末尾函数结果帧，2000层JSON | 对应条件fail/behavior，监督进程正常完成 |
| 既有完整run驱动 | 三题正确实现100分；典型错误、语法、证据缺失/损坏、预算分类均通过断言 |
| stdout/stderr分别超限、候选超时 | 均为对应条件fail/output_limit或timeout |
| 正常/异常/超时/超限，后代持有管道 | 既有判定及候选/后代回收断言均通过 |
| 78条件全超时 | completed/fail，0分，32.044秒；部分预算不足仍error并保留not_run |
| 既有资源参数与插件宿主SIGKILL | CPU45秒/AS512 MiB/FSIZE1 MiB断言通过；候选与后代已回收 |
| 真实ProcessWorker三题 | 均100分，约2.068/1.952/5.861秒 |
| 真实ProcessWorker进程组SIGKILL | 观测到的24个监督/候选/后代PID全部从/proc消失 |

上述耗时包含启动开销；并行验证有资源竞争，不能作为性能基准。
新增EOF场景均检查有界完成及PID消失；深层CLI用完整score验证其他条件继续执行。

深度错误验证补充：初次regressions通过，但仅有行为fail不足以证明进入RecursionError
分支。增加“材料必须触发RecursionError”断言后，驱动退出1：默认C解码器接受2000层。
随后独立探测确认30000层也被接受，不能将原通过结果称为深度异常路径覆盖。
为真实覆盖异常分支，新增verification/python_json.py，仅在验证启动器里选择标准库的
py_make_scanner；启动器先确认同一2000层材料实际抛RecursionError，再执行原scorer.py。
regressions先跑默认解码器，再临时将监督启动入口指向该验证启动器，最后恢复。
未替换score/supervise、候选、收集或回收函数，未改变生产解码器配置。
因此默认环境结果与强制标准库递归解码器结果分别报告；后者属于定向验证配置，
不能声称默认C解码器已复现深度异常。两种配置的CLI均completed/fail 50分、17条件全执行，
末尾函数帧均fail/behavior。首次递归解码器运行退出1，CLI曾错误得到100分，暴露上述
passed真值残留；显式重置后两种配置复验通过，最终regressions退出0。
另外补充两种解码器下普通畸形JSON的同路径回归，均completed/fail 50分。

## 静态检查与摘要

Windows/PowerShell实际执行：

```powershell
uv run --no-sync python -m integrations.coding.validate
uv run --no-sync ruff check src migrations integrations/coding
uv run --no-sync ruff format --check src migrations integrations/coding
git diff --check
```

均通过。离线校验仍为18/17/78条件，数据集config SHA-256未变化：
`1c518bb176522261c3b98598f87d693d6f334a5e992fb695461a7cf0a10439c1`。
未运行前端、迁移或数据库检查，本轮不涉及这些代码。

评分器SHA-256按原始文件字节计算，自动摘要只覆盖scorer.py：

- 修复前Git blob（LF）：`2b5c6fa9a12c2c6055c62ccf916b470670f09397fff378d99e4e3f40a98672b1`。
- 修复后Git内容（LF）：`b6778789bbe44cf1e83787a1202c7ba237e9a404856375bee9b752ce1a465511`。
- 本轮Windows文件及容器只读挂载文件（CRLF）：`f50c422eaf47ed6aa511acc28690df39957d2ce1b003955cef38be514fcacfad`。

换行影响字节摘要；未来部署须核对实际安装文件摘要，另获授权发布新ScorerVersion，
不得复用旧版本。本轮没有发布，也没有改变任何历史评分或报告。

## 剩余限制

未注入内核wait/kill故障来动态制造无法确认回收；该error路径只经源码核查，未记为运行复验。
未覆盖候选逃逸进程组/新建会话、树总资源限额、长期负载、真实Agent与历史重评分。
独立进程不是安全沙箱，原实施记录中的未覆盖边界继续保留。
