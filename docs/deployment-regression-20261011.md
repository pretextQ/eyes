# 部署安全头与版本回归验收

日期：2026-10-11（Asia/Shanghai），开始基线 `261931d`。本轮遵循 [开发约定](../AGENT.md) 与 [计划](PLAN.md)，不重新实现前三个开发任务，不新增或修改测试、评测用例、fixtures、mocks 或模拟数据。私有原始响应、失败和运行材料保存于 Git 忽略的 `data/deployment-regression-20261011/`。

## 审查 #1：nginx 安全头

在两个声明缓存头的 location 内显式重复已有 `X-Content-Type-Options: nosniff` 和 `Referrer-Policy: same-origin`，避免 location 的 add_header 覆盖 server 级继承。没有增加 CSP、其他安全头或更改缓存、SPA 路由、API 代理。

本机 Docker Linux 实际拉取的 `nginx:stable-alpine` 为 **1.30.5**，镜像摘要 `sha256:0985e772fb9f729e6fa0980da05fca5d9c468e870eed43071545afa9d2e27d94`。采用显式声明方案也兼容未支持 header 合并指令的旧部署版本。`npm run build` 与容器内 `nginx -t` 通过。

独立容器 `eyes-deployment-web` 使用仓库 nginx 配置与真实前端构建产物，端口 18084；代理连接隔离安全验收 API 18056 / PostgreSQL 55443，未故障注入已有 MewCode 重验服务。通过实际 HTTP GET 记录 `headers.json`：

| 响应 | HTTP | 两项安全头 | 缓存 / 路由结果 |
| --- | --- | --- | --- |
| `/`、`/index.html`、SPA 深链 `/experiments/history/deep-link` | 200 | 均保留 | HTML、no-cache |
| 实际构建的 `/assets/index-*.js` | 200 | 均保留 | max-age=31536000、public、immutable |
| 不存在的 `/assets/missing.js` | 404 | 均保留 | 不回退 SPA，不附加成功缓存策略 |
| `/api/health/ready` | 200 | 均保留 | 实际 API ready、0005 |
| 未认证 `/v1/experiments` | 401 | 均保留 | 保持认证拒绝 |
| `/openapi.json`、`/docs` | 200 | 均保留 | 保持 API 文档代理 |

环境准备失败原样保留：首次 pg_ctl 输出路径不存在，随后正确路径启动成功；API 早于数据库启动而退出，导致 nginx 首次无法解析 api 上游。按依赖顺序重启后才进行上述 HTTP 验证。配置检查没有被用来代替 HTTP 结果。

## 审查 #4：比较实验选项缓存

普通创建与详情页关联重跑共用 `CreateExperiment`，失效键改为实际查询的 `comparison-experiment-options`；批次创建同时失效该键。其余用例工作台操作采用全量失效，未发现同类遗漏；取消不新增实验，保持现有失效策略。

前端 lint、format:check、build 通过。使用同一浏览器会话连接隔离真实 MewCode 项目，先加载比较创建页的两项既有实验；通过 Web 使用既有目标、原三任务数据集及原评分器创建实验 `7a551a6e-e1ce-4665-b786-6fde6c139991`，经应用导航返回比较页，无刷新、重连或手动刷新，新实验立即出现在基线/候选选项。随后 Web 创建单真实成员批次 `8dc466d3-156d-4ed2-8767-798524d01df4`，成员 `5f0a65eb-e690-4466-8f82-ee7c8398729e` 同样立即出现。保存 before/after 与 batch-options 的实际页面文本/截图；没有构造演示数据，未启动原项目 Runner。

## 审查 #2：取消语义与审计缺口

不新增实验 cancelled 终态。`completed` 表示调度结束，Attempt / CaseRun 取消事实独立保留。源码核对 `cancel → refresh_experiment → summary → comparison.capture`：排队执行取消后 CaseRun=cancelled；等待/排队评分 skipped，活动评分记录取消时间并拒绝将后续结果计为有效分数；尚未确认停止的执行继续 cancel_requested / unknown 并保留额度。

本轮通过公开 API 取消上述新建普通实验和新批次：各三个 CaseRun 均 cancelled、没有 Attempt；汇总 completed、cancelled_runs=3、计划=3、执行成功=0/3、有效评分=0、评分覆盖=0/3、通过率分母=0。Web 逐用例显示“已取消”，没有执行/评分成功显示，详情已有“已完成表示调度结束”的说明。固定报告展开显示候选已取消、execution_not_successful、未选出成功执行/评分；三项 inconclusive，改善/退化均为 0。默认门槛因执行成功率不足为 fail，同时保留缺口。未发现需要修改的明确显示错误，未改变公共状态机。

**独立设计缺口**：Experiment 没有取消请求的独立时间、操作者、理由或持久化审计记录。活动 Attempt/ScoreRun 的取消时间及排队用例 cancelled 能保留部分事实，但无法完整重建实验级取消意图（尤其调度终态后）。将来应单独评估追加审计事实及权限/历史读取，不能据此未经评估改变 completed 的公共含义。本轮仅覆盖排队执行取消；没有宣称 MewCode 不支持的远端取消正向路径已通过。

## 安全恢复前置条件复核

新版本执行前，只读复核上一轮的原始响应、PostgreSQL 当前状态与 Agent protocol.sqlite3，没有重跑原操作。记录为 `safety-prerequisites.json` / `safety-raw-verification.json`：

- 整体退出原操作仍只有一个 Attempt、一个原幂等键对应的远端 run；历史真实转换 running/reserved → unknown/reserved → succeeded/unreserved，远端真实结果 stopped_confirmed=true。
- 两 Runner 竞争只有一个得到 query；持有中的查询重启前后 count/token/due_at/expires_at 一致；可信终态 applied=true 仅一次，迟到观察 late=true/applied=false，重复结果 HTTP 200/duplicate=true。
- 未确认原任务仍 unknown/reserved=true、仅一个 Attempt、applied=0、远端停止未确认。失败查询重启前后记录有后续查询，count 从 1 增至 2、due_at 向后推进，并非整份 JSON 完全相同；当前持久状态 count=3，没有重置或解除额度。此边界按实际材料记录。

指定安全恢复必需项沿用已核实的真实证据，可开展本轮版本回归；这不升级完整 M2。此前默认与显式报告的 content/digest/request_digest/id 在本轮再次通过只读 API 核对不变。

## 同一真实 Agent 的不同版本

Eyes 运行基线 `4ab8a73`；Windows 11 / Docker Engine 29.8.2，本机 Linux CPython 3.14.7、PostgreSQL 15.17 / 0005。使用既有缓存运行镜像 `sha256:420dba75f4b41b95976e91e0d590cfc9d1fb3397a8a64b39c1c21ed167ceca2a`，保存实际依赖，未声称完整锁文件部署已验收。

通过 `git archive` 原样导出同一个 MewCode 仓库的两个真实提交，只读挂载，不 checkout 或修改外部 Agent、测试集或评分器。正式验收在 **verified-versions-final/** 的新项目、新 Agent 状态、新 Runner 状态和限定目标凭据中进行；Agent 只挂载自身状态及必要源码/参数，不挂载管理/Runner 凭据目录。容器进口路径与全部 Python 文件 SHA-256 映射在业务运行前完全匹配对应导出源码。

| 角色 | MewCode 提交 | 源码映射摘要 | 实验 |
| --- | --- | --- | --- |
| 基线 | `9282caa1f769ce4d8b6f8f47624eedfe9847f8c1` | `6cd3a5d15d41c449c313e88fedc423f51c27c825671277ead0d41704aa4a4791` | `4d7fed08-087a-4f8f-8a1d-84723c14495a` |
| 候选 | `3f104082b6c5ca53efe273630bf08f67f1fc3ff5` | `b29a77964163dcf5a10d32d386e1d16144aa3f0f4780ff829123bcf170729ead` | `bb758f8b-4d71-428e-84e6-234289458c5b` |

两个版本之间存在真实 bash/进程树处理及服务取消修复，未人为制造输出差异。基线仍缺后续进程树停止修复，本轮仅运行既有正常任务，不开展该版本的超时/取消正向验收；独立容器是运行隔离，不能宣称任意代码安全沙箱。

固定原 `integrations/deta/coding-smoke.jsonl`（SHA-256 `9e868ae0c53f1e2f88d6114b5c76e591647ecd78ef6b6d3882cbaf8b49771e4b`）和当前既有 `scorer.py`（文件 SHA-256 `3e72cfd6a721cddd420f9d850cf79366545e886ec59b7377424c01fb0737d826`），同一发布数据集及评分器。评分器直接复用上一轮发布内容，不新增用例。两个实验除 target_version_id 外请求配置相同：并发 1、重复 1、超时 300 秒、证据等待 15 秒、first_success。Agent 参数文件相同，DeepSeek/deepseek-flash、thinking=false、context_window=128000、max_output_tokens=8192、最多 12 轮。模型别名没有固定远端权重；原用例的外部环境限制继续保留。

### 实际结果及可比性

两个版本各三个真实 Agent 执行，fix-mean / integer-cli / stable-unique **全部 succeeded、独立评分 completed/pass，各 4/4 原功能检查**。两侧计划/成功/有效评分/通过均为 3，失败、unknown、取消和未解决评分均为 0。执行成功率、评分覆盖率、有效评分通过率均有实际分母 3/3；每个用例只运行一次，不提供稳定性结论。

正向报告 `8127257e-0a5d-41f9-87a5-acd0fddb019b` 和反向报告 `50233964-d04b-482f-8213-5e95cca26d79` 均可比覆盖 3/3、三项 unchanged、改善=0、退化=0、门槛 pass。相同用例摘要、评分器完整摘要、执行配置和采集能力通过核对。目标配置仅 URL 与 discovery 不同（隔离服务端口及真实版本发现），报告保留配置变化提示，外部环境限制也正确显示。

**真实改善与退化仍未覆盖**：既有三任务和两个可追溯版本都通过，无法提供至少一次改善和一次退化。反向比较同样无变化，不能将反向运行、取消、部署故障或不同 Agent 的通过率冒充版本质量退化。不修改外部 Agent 或任务来制造结果；M3 的完整验收仍受该证据缺口阻塞。

### 历史选择、证据和 CLI

- 正式六个 ScoreRun 的 Runner 原始冻结 payload、公共 Attempt manifests 和报告 ID/摘要对应；评分引用均在授权证据视图，清单均属对应 Attempt。实际下载 16 份冻结产物，HTTP 成功、大小/SHA-256 全部匹配，保存 `version-evidence-links.json`。追加评分的清单/引用也通过核对。
- 对候选真实 fix-mean 显式 rescore，运行原评分器，新 ScoreRun `341c2fe1-0420-45da-bf04-48e11cde64cf` completed/pass。新默认报告仍选择原最早的 `7de76619-9f34-4b30-b0a5-ada9c61b77fa`；显式报告 `dddde83a-3509-46c1-b63b-8d160d77d912` 绑定新记录。候选原三评分逐项相同，旧默认报告 content/digest/request_digest/id 全部不变。Web 展开默认/显式报告也显示正确的 Attempt/ScoreRun/Manifest 与两条引用。
- 实际运行当前 CLI `python -m eyes.cli.main --url http://127.0.0.1:18056 gate <report-id>`，令牌仅通过环境变量传递：

| 真实条件 | 退出码 | 证据限制 |
| --- | --- | --- |
| 两真实版本无变化且全部达标 | 0 | 是真实 pass，不是改善证据 |
| 另建同配置实验并在 Runner 停止时实际取消三个排队用例；默认门槛 | 1 | 真实执行成功率 0/3，不是质量退化 |
| 同一真实取消事实，单独报告设 min_execution_success_rate=0 | 2 | 保留 no_valid_scores 与可比覆盖缺口，无伪造结果 |
| 使用无效凭据读取真实 pass 报告，实际 API 401 | 3 | 认证错误路径，不代表全部配置/服务故障已穷尽 |

原始 gate stdout/stderr/退出码保留；报告参数和结果由公开 API 生成。页面无变化、可比性、分母及默认/显式证据绑定已实际核对。

### 必须保留的首轮失败

首轮六个真实执行及七个评分虽通过，但源码摘要核对发现 Docker 的显式 PYTHONPATH 覆盖 service.env，载入了缓存镜像内的 MewCode：基线共享源码有 67 个文件摘要不一致。**整轮排除版本回归验收**，保留容器、运行数据和报告，未改写其 external_version 或结果。随后第一次重新部署遇到原端口占用，保留失败日志，没有执行任务；最终用新目录和 19053/19054，业务运行前两个版本源码摘要完全一致，才纳入上面的六个执行及七个评分。

采集器首次调用不存在的 ScoreRun GET 得到实际 404；改用保留的真实冻结 payload 与公共 manifests。另一次读取产物元数据层级错误 KeyError 也保留，修正后才完成下载校验；不是平台或评分失败。失败清单、组件日志、部署参数、源码摘要和全部私有记录不提交。

## 验收状态与未覆盖项

本轮确认 #1 的本机隔离部署（最终新构建 assets GET 200 / 条件 GET 304 同样保留两项安全头）、#4 的真实项目创建交互、#2 的既有取消显示语义、安全恢复必需项证据以及同一 Agent 两个可追溯版本的无变化回归、历史选择/引用/分母和 CLI 0/1/2/3。

未覆盖：真实改善/退化、远端取消正向、所有历史评分/缺版本组合、所有 gate 错误分支、完整 M2、干净完整 Compose、完整证据备份恢复、容量和长期运行。本轮没有处理全局锁、轮询或索引，没有新增或修改仓库测试/评测用例。M3 **部分验收，不能宣称完整通过**。

收尾：本轮新增 Runner 已正常停止；新旧两轮 Agent、nginx 验收容器及本轮重新启动的安全 API/PostgreSQL 已停止，状态目录和容器均保留。此前仍在运行的 MewCode 重验 API/Agent 未中断。静态检查与文档链接/diff 检查结果和本轮 Git 发布分别核对，文档不包含凭据或私有运行载荷。

## 补充：真实改善/退化候选检查与阻塞

2026-10-11（Asia/Shanghai），Eyes 基线 `5233701fa3f1710fe4e7c18c8c8388bfa4c8c443`，开始时 `main` 工作区干净。本次仅推进真实版本质量变化验收，不重新开发回归功能。阅读开发约定、README、架构、PLAN、本页、MewCode/Python 与 HTTP 验证、Runner 可靠性及回归口径说明后，定向检查 `D:\projects\MewCode` 的版本历史和本页已有私有材料。

实际执行 `git -C D:/projects/MewCode fetch origin` 成功；本地 `master`、远端 `origin/master` 均为 `3f104082b6c5ca53efe273630bf08f67f1fc3ff5`，外部 Agent 工作区干净。检查 Agent、client、工具、权限、prompt 与配置相关历史，没有 checkout 或修改外部源码；远端没有比既有候选更新的主线版本。`origin/ci-logs` 是日志分支，未把其记录当作新增 Agent 实现。没有扫描无关项目或安装依赖。

### 已检查的真实候选

通过只读 `git show/log/diff` 检查以下真实变化，并对 15 个提交使用内存中的 `git archive` 计算全部 `mewcode/**/*.py` 字节摘要。这里的摘要是 **Git 源码候选摘要**；除既有两个正式版本外，没有新的容器加载核对或业务执行，不能称为实际运行版本。

| 候选提交 | 实际源码差异 | 固定三任务/当前接入下的判断 |
| --- | --- | --- |
| `90918c6` → `7152ddf` | 工具相对路径从进程 CWD 改为绑定 work_dir，新增 `ToolRegistry.bind_work_dir` | 是相关行为修复，但旧侧缺少 bridge 无条件调用的方法。原接入会在业务前失败，不能将接入故障算作质量退化；不修改 bridge 或旧 Agent 绕过此边界 |
| `f86827b` | 子 Agent 三条创建路径绑定工具 work_dir | bridge 直接创建主 Agent 和默认六工具，没有注册子 Agent 工具；不是现有路径的质量变化证据 |
| `c0080ef` | `run_to_completion` 环境注入及 compact 后恢复 | bridge 调用 `Agent.run`，未调用该入口；不能用不同入口的修复声称现有任务改善 |
| `a1fe065`、`539ae2b`、`e72ffc2`、`a9acd9b` | thinking 预算/截断恢复、未知工具连续中断结果补齐、空消息防护、OpenAI 输出上限与截断信号 | 固定 thinking=false、8192 输出上限和正常六工具；已有材料没有提供这些恢复条件导致代码质量 fail 的可比两侧证据。输出截断修复确有行为差异，但不能靠降低预算、制造错误或盲目重复运行触发它 |
| `02543a6` | 文件编码/行尾保留、CRLF 匹配及编辑历史记录时机 | 既有输入是 UTF-8/LF，执行在 Linux；bridge 没有启用编辑历史。没有已知对应功能检查失败，不改输入或切换操作系统制造差异 |
| `7f50a5b`、`e83a496` | 读取/扫描移出事件循环，grep 限制；rewind 缓存失效与空缓存判断 | 三任务是小文件功能检查，不评分扫描吞吐；bridge 不传 FileCache、不调用 rewind。没有质量变化材料，不开展容量试跑 |
| `2236900` | 子进程环境白名单、密钥变量展开、MCP transport 配置 | bridge 传入实际密钥、未接入 MCP；配置/认证问题不能当质量退化 |
| `9282caa`、`1d3daab`、`3f10408` | shell 环境说明、超时/取消进程树清理、服务事务取消所有权 | 两个正式版本已经各 3/3 pass；中间提交的主要变化是清理。原任务正常完成，没有可比质量 fail；不重复超时/取消验收或把可靠性故障当质量变化 |

这些排除依据是源码与既有材料的定向判断，**不是证明所有历史版本在本测试集永远同分**。兼容旧版本仍可能产生不同模型输出，但当前没有足够依据选出会触及既有评分条件的真实缺陷版本；为了碰到偶然失败而连续试跑不满足本轮要求。

源码映射摘要按 `SHA-256(json.dumps(按路径排序的 Python 文件 SHA-256 映射, sort_keys=True))` 计算，与此前正式记录口径相同：

| 候选 | Git Python 源码映射摘要 |
| --- | --- |
| `90918c6ac3272cc0c02613efb31ef5b0318dd7e5` | `e9bd6f88cc27868efc0eedfa0f701805645fe4afeb4ccaa14549391e6f113911` |
| `7152ddf75b9dabb579d3ec798783ef77151bc20a` | `cad65a85b6325fb7948bf3c8a39d2df4ad71530eea1c99ddf40348fcd47f548d` |
| `9282caa1f769ce4d8b6f8f47624eedfe9847f8c1` | `6cd3a5d15d41c449c313e88fedc423f51c27c825671277ead0d41704aa4a4791` |
| `3f104082b6c5ca53efe273630bf08f67f1fc3ff5` | `b29a77964163dcf5a10d32d386e1d16144aa3f0f4780ff829123bcf170729ead` |

其余候选的完整提交、每文件映射与集合摘要保存在新建且 Git 忽略的 `data/real-version-quality-20261011/`：`candidate-audit.json`、各提交 `*-source-hashes.json`、`agent-history.txt`、`agent-core-diff.txt`。仅保存只读检查材料，没有覆盖旧实验、评分、报告或运行目录。已有 `data/mewcode-regression-20261009/` 为空，没有可用的额外版本质量材料；此前 Python/HTTP 记录中的失败是产物部署/缓存接入问题，不能复用为质量退化。

### 既有事实、执行边界与状态

从 `verified-versions-final/` 原始 case-runs、results、source-identity/source-hashes 及固定报告摘要定向核实：两个源码映射与对应 Git archive 完全一致，六个原始用例都只有一个 Attempt，均 succeeded；六个原始 ScoreRun 均 completed/pass、各 4/4。既有正反向报告仍为可比 3/3、unchanged=3、improved=0、regressed=0、gate=pass。这是读取已有证据，不是新一轮独立评分或 API/CLI 复验，也不重复已通过的历史选择、引用和 gate 检查。

数据集文件 SHA-256 仍为 `9e868ae0c53f1e2f88d6114b5c76e591647ecd78ef6b6d3882cbaf8b49771e4b`，评分器文件仍为 `3e72cfd6a721cddd420f9d850cf79366545e886ec59b7377424c01fb0737d826`。既有配置与实际环境沿用上节记录：串行、重复 1、first_success、300 秒、证据等待 15 秒，DeepSeek/deepseek-flash、thinking=false、128000 context、8192 输出、12 轮，Windows 宿主机/Linux CPython 3.14.7/PostgreSQL 15.17。模型别名及外部环境限制继续保留，不推断固定权重或稳定性。

**本次结果：候选检查已完成，真实改善/退化验收阻塞。** 新执行=0、新评分=0、新报告=0。未找到具备既有任务质量差异依据且满足当前接入/可比环境的版本对，按要求停止试跑；没有发现需最小修复的 Eyes 明确缺陷。未启动或改动已有服务，没有新增测试、评测用例、fixtures、mocks、模拟数据或依赖，没有提交原始日志/私有数据。

状态区分：回归功能**已实现**；两真实版本无变化及此前列出的默认/显式评分、旧报告、证据引用、分母与 CLI 路径**已验证**；固定既有测试集下至少一项真实改善与退化仍**待验证且阻塞**。解除阻塞需要同一 Agent 的可兼容真实版本，并有既有三任务对应的实际质量失败/修复依据或可比历史材料；不能用另一个 Agent、改变任务/评分器/参数，或偶然失败挑选代替。本次不更新 M3 为完整通过，纯验收文档集中提交，不要求推送。

本次文档检查：两份修改文档的本地文件链接均存在，新增章节锚点对应，`git diff --check` 通过；Git 修改范围仅本页和 PLAN。没有产品代码修改，未重复运行静态构建、仓库测试或已通过的业务验收；这些文档检查不算真实改善/退化验证。
