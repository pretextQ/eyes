# 干净部署、独立接入与权限验收

日期：2026-10-11（Asia/Shanghai），开始基线 `9281a076d0d1a01dae7ae9a136375475cb891fb1`，分支 `main`。本轮只推进干净部署、独立接入和权限，不重做完整证据备份恢复，不扩展新功能。依据 AGENT、README、PLAN、Compose/Dockerfile、Agent/观测接入说明及[已有完整恢复记录](backup-release-review-20261011.md)。

## 干净控制平台与目录权限修复

Docker Engine 29.8.2。新项目 `eyes-clean-20261011`，API 18064、Web 18086、PostgreSQL 55446；独立网络、新数据库/证据卷。启动前保存原容器和卷清单，未启动、覆盖或删除原服务及数据。新私有材料位于 Git 忽略的 `data/clean-deployment-20261011/`，Windows 目录 ACL 仅当前用户。环境、令牌、构建/运行日志与响应均不提交。

实际执行仓库 `deploy/compose.yaml`，使用独立环境文件及 `-p`，`build --no-cache --pull`；没有用已有 `eyes-mewcode:local` 镜像。后端 Dockerfile 用 Python 3.14.7、uv 0.12.2，实际运行 `uv sync --frozen --no-dev`；前端 Node 24 的空构建层实际运行 `npm ci`、`npm run build`。首次构建与 `up --no-build -d` 均退出 0。PostgreSQL 18.6 健康，migrate 退出 0，API 健康、Scheduler 持续运行、Web 首页及代理 readiness 为 200。宿主机 `alembic heads` 和新服务 `alembic current` 都为 `0005_reconciliation`；新库 `alembic check` 通过。执行首次 bootstrap 创建两个独立真实项目，并分别签发 read 凭据；没有恢复旧库或预置业务数据。

**明确部署缺陷及最小修复**：初始 API 身份为 UID/GID 10001，但镜像初始化的 `/app/data/artifacts` 为 `10001:10001 / 0755`，UID 65534 实际可以列目录。`deploy/Dockerfile` 只追加 `chmod 0700 /app/data/artifacts`，保持原运行身份和产物发布逻辑。重新无缓存构建控制镜像，采用新的 `eyes-clean-20261011_artifacts-private` 卷启动；原初始空卷保留，没有在旧卷上隐藏失败或放宽权限。新目录实际为 `10001:10001 / 0700`，UID 65534 列目录返回 permission denied / 退出 2。API readiness=200，服务用户 `eyes-ops audit` 为 ok（当前尚无业务产物）。README 明确新卷权限及已有卷不自动交接的边界。真实产物授权下载在后续接入阶段验证，空卷 audit 不代替它。

前端干净安装报告 7 项 high：链路来自 devDependency `shadcn` 及 registry/ts-morph/glob/braces。保留实际 `npm audit --json` 和锁文件摘要，未运行 audit fix 或升级依赖。影响核查见末节，不能因构建成功宣称依赖安全。

独立 Agent/Runner 最小真实闭环、完整权限矩阵及产物下载仍在本轮继续验证；本节只记录已完成的部署与权限修复，不宣称全部 M4 通过。

## 接入构建修复及已通过的检查

旧 `integrations/mewcode/Dockerfile` 没有 COPY Eyes 锁文件，使用浮动 uv 与非冻结 `uv pip install /app /opt/mewcode`；不能按仓库锁文件独立复现。最小调整为与控制镜像相同的 Python 3.14.7/uv 0.12.2，先 `uv sync --frozen --no-dev` 安装 Eyes，再导出外部 MewCode 非开发锁定依赖，安装当前环境缺少的包和 Agent。共享依赖不覆盖，最后 `uv pip check` 必须通过；不改外部源码或两份锁文件。同时将该镜像的新证据目录设为服务用户私有 `0700`。接入 README 增补干净构建、依赖边界、HTTP 服务必需变量、独立状态卷和分离 Runner 的实际步骤，避免固定旧脚本覆盖历史目录。

保留本轮第一次实现检查失败：依赖过滤误用了系统 Python 的 metadata，第一次镜像构建及 pip check 虽成功，逐项核对发现 14 个 Eyes 锁定包版本被替换。该镜像未运行 Agent 业务；改用 `/app/.venv/bin/python` 获取已冻结环境后，重新 `--no-cache --pull` 构建最终 `eyes-clean-mewcode-verified:20261011`，再核对共享包与干净控制镜像完全一致、pip check 通过，才启动业务。此前用于检查组合安装方法的独立私有镜像也保留，不作为文档构建证明。

实际 MewCode 提交 `3f104082b6c5ca53efe273630bf08f67f1fc3ff5`，运行容器全部 Python 源码与干净 Windows checkout 逐文件一致，实际源码映射摘要 `a007cfa9bcfb9d2f1051a154c6f64d2b42542fc83061d45ba046787d0b94e35d`。Git archive 的 LF 字节与 Windows checkout 行尾不同，不能将这项首次候选摘要比较不一致误报为加载缓存源码；随后明确比较实际 checkout 与运行字节。外部模型配置沿用已有无密钥参数和运行时密钥，未写入镜像或发布配置。外部 Agent 是真实执行目标，不是控制平台缓存运行镜像。

最终镜像已通过真实 HTTP 发现/能力读取，Agent 可加载、状态目录可写；干净控制镜像中的独立 Runner plugins 读取到原评分器文件摘要 `3e72cfd6a721cddd420f9d850cf79366545e886ec59b7377424c01fb0737d826`。新项目导入原完整三任务，签发限定目标与工作类型的凭据。真实闭环和权限矩阵的最终结果随后记录，不以构建/发现代替执行成功。

## 独立真实闭环结果

按文档从新 bootstrap 项目发布目标、原数据集及原评分器，HTTP 发现真实 MewCode 后，启动两个新的非 root Runner：一个仅 execute、score_slots=0，另一个仅 score、execution_slots=0；分别有独立凭据、状态卷。Runner/API/Scheduler 不连接任何旧数据库，Agent 不挂载项目管理或 Runner 环境文件。HTTP Agent 状态卷与控制证据卷完全独立，沿用已有模型运行时密钥及参数，不改外部 Agent 核心。

正式实验 `7fd2080c-1545-4747-be14-60cef6cab405`，固定原三任务（数据集文件 SHA-256 `9e868ae0c53f1e2f88d6114b5c76e591647ecd78ef6b6d3882cbaf8b49771e4b`）、原评分器；并发 1、重复 1、first_success、执行 300 秒、证据等待 15 秒、评分 40 秒。模型仍是 DeepSeek/deepseek-flash、thinking=false、context_window=128000、max_output_tokens=8192、max_iterations=12。远端别名不等于冻结权重；只证明本次基础闭环。

| 既有用例 | 实际执行/清理/证据 | 独立评分 |
| --- | --- | --- |
| fix-mean | succeeded / succeeded / sealed，一个 Attempt | completed / pass，4/4 |
| integer-cli | succeeded / succeeded / sealed，一个 Attempt | completed / pass，4/4 |
| stable-unique | succeeded / succeeded / sealed，一个 Attempt | completed / pass，4/4 |

计划=3，执行成功=3/3，有效评分=3/3，通过=3/3；失败、unknown、取消及未解决评分均为 0。真实材料有 56 条事件、8 份产物、6 份清单、3 个独立 ScoreRun。read 身份下载全部 8 份产物，HTTP 200，保存的实际响应字节大小/SHA-256 与冻结元数据全部一致。服务用户 audit 为 ok，8 ready/6 manifests/3 scores；两个 Runner 的 pending/rejected/orphaned/corrupted/quarantined 均为 0，score Runner retained_work=3 是保留的评分目录，不是活动工作。

最终控制镜像 ID `sha256:4775a9362087d827e6131e51be73c0e970aaf88b247d606c9142c892daa2ab82`，文档 Dockerfile 构建的 MewCode 镜像 ID `sha256:38d79560bd89a8cb426375ee7be2f18252ec4964fd3ddf7997a3068ffc143dd5`。API 和 Agent 实际加载的 Eyes Python 文件均与本次宿主机源码逐项一致；最终实际依赖及两份锁文件摘要另存私有材料。没有通过复制缓存 site-packages 绕过干净构建。

本轮完成按文档操作的新环境 HTTP 接入；这不是另一个人在另一台机器上的独立验收，也不把同一 MewCode 的两种接入方式称作两个不同 Agent。此前 Python 基础闭环仍按历史记录保留，本轮没有重复新环境 Python 接入、第二个真实 Agent、可选取消/资源或恢复矩阵。

## 实际权限矩阵

下面请求使用本轮真实项目、发布版本、运行 Attempt、原事件、产物、原租约身份及实际创建的来源，不制造执行结果或用模拟业务数据替代。共 **131 个具名 API 权限请求**，实际状态码全部与预期一致。逐请求身份类别、端点、实际状态、错误码和原始响应保存在 `permission-matrix.json` / `permission-*.json`；这个数量不代表所有接口/参数组合已穷尽。正向执行/评分上报另由上述真实 Runner 完成。

| 范围 | 实际允许 | 实际拒绝/隔离 | 边界 |
| --- | --- | --- | --- |
| read/manage | 两者读取 catalog 版本、实验/结果/用例、Attempt、事件/清单、operations/contracts、来源/观测列表和产物均 200；manage 已实际发布、导入、创建实验/来源及撤销来源 | read 发布目标/评分器、导入数据集、创建/取消实验、rescore、创建/撤销来源均 403；缺认证读取实验 401 | 没有据代表性端点宣称所有管理分支穷尽 |
| 跨项目 | B 的列表只含本项目数据，实验列表为空 | B 的 read/manage 读取 A 的实验、结果、用例、Attempt、事件/清单、target/dataset/scorer 和产物均 404；B 创建引用 A 版本的实验、撤销 A 来源均 404 | 第二项目及其目标是真实 bootstrap/发布的行政对象，不是模拟 Agent 输出 |
| Runner 目标范围 | 限定目标的 execute/score Runner 实际分别完成三个执行和三个评分 | 另一目标凭据对 A 的实际排队执行请求返回 200/work=null；其对已有工作为 403/work_scope，Attempt 写入及产物读取为 403；跨项目 Runner 对 A 的 Attempt/产物/工作为 404 | 第二目标是同一真实服务的另一个发布目标，用于范围检查，没有制造质量对比 |
| Runner 工作类型 | execute-only 与 score-only 各自完成授权工作；两者可下载各自工作授权的实际产物 | execute 凭据领取 score、score 凭据领取 execute 均 403/work_kind；score 凭据写入执行事件、登记执行产物或封存均 403 | score-only Runner 对 reconciliation 的 403 保留在原日志，未放宽权限；没有需要该路径的未知任务 |
| Runner 身份/Attempt | 原 execute Runner 重传原事件 200（去重）、原产物元数据 201（同一登记）、原封存 200；原 score Runner 实际读取固定清单产物并提交评分 | 同项目同目标但没有该 Attempt 的另一 Runner：事件/登记/封存/下载 403；其操作别人的 work heartbeat/score-input 为 409/stale_lease；借用原 Runner ID 为 403/runner_identity | 重放原事实，不添加新事件或手写执行/评分结果；历史终态原工作授权下载仍允许，符合当前实现 |
| 观测来源与项目凭据 | manage 创建/读取来源 201/200；来源令牌 heartbeat 为 200/accepted=false | 项目 read/manage/Runner 凭据调用来源 heartbeat 均 401；来源令牌读取项目/产物/观测列表及管理目标均 401；read 撤销来源 403，其他项目撤销 404；通用 factory 的本地无令牌入口 403/local_only | heartbeat 使用真实 HTTP operation ID，但没有对应 ObservedRun，**只覆盖来源认证，不代表正向事件接入成功** |
| 撤销 | 专用 read/manage 凭据撤销前下载 200；两个实际 Runner 对未过期产物撤销前下载 200 | 撤销后同一下载均 401；另一已注册 Runner 撤销后注册 401；manage 撤销来源后 heartbeat 401 | 不用恢复工具的旧 Runner 撤销代替本轮实际 revoke-token；没有撤销原项目凭据 |
| 过期证据 | read 仍可读取带 expired 标记的 Attempt/清单历史，已有评分理由保留 | 已授权 read/manage/execute/score 下载过期产物均 410；原 execute 事件重传/产物登记 410；manage rescore 410；跨项目下载仍先返回 404 | 对本轮一个已完成真实 Attempt 先 preview，再执行正式 eyes-ops maintain --attempt-id --apply；没有修改数据库时间或伪造过期状态 |

过期操作只针对本轮 `ce26b647-e1a0-4bce-b8e8-211a0cd14f1d`，删除该 Attempt 三份真实产物文件，delete_failures=[]；后续服务用户 audit 仍为 ok，ready=5、expired=3、manifests=6、scores=3。私有采集目录保留此前下载的原字节；原环境证据和本轮其他两条 Attempt 未过期。这里只验证过期访问边界，不重复备份恢复或宣称生命周期故障矩阵完整。

**观测正向材料缺口**：本轮和已有恢复材料的 ObservedRun 都为 0，没有可重放的真实 ObservationBatch，也没有在本轮接入真实 exporter。因此未验证正向 `/observation/events`、真实观测详情的跨项目/跨来源归属、来源事件重传及 exporter 缓冲恢复；没有把执行 SDK 事件伪装成观测 exporter 数据。后续需真实来源材料补齐这一部分。

## 身份、私有存储、Web 与依赖影响

控制 API/Scheduler、Agent、Runner 均以 eyes UID/GID 10001 运行；控制证据根 `0700`、产物 `0600`，Agent 状态根 `0700`、protocol.sqlite3 `0600`。PostgreSQL 服务进程 UID 999，实际 PGDATA 为 999:0 / 0700。nginx 1.30.5 使用其镜像默认 root master/UID 101 worker，只提供构建后公开静态内容和 API 代理；未在前端容器放置项目/Runner/model 凭据或挂载证据卷。没有把 Docker 管理者/root 可访问卷的能力当作应用 ACL 能防御的对象。

API readiness 与 Web `/api/health/ready` 均 200；真实构建首页、实验 SPA 深链及全部首页引用 assets GET 均 200。read/manage 经 nginx 代理查询本轮结果均 200，授权下载及 service-user audit 已如上验证。本轮没有 UI 改动；HTTP/bundle 检查不宣称浏览器所有交互和断点已验收。

依赖核查：实际 npm audit 7 项 high 的根因是锁定链路中的 `braces <=3.0.3`；[GitHub 已审核公告](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)说明深层嵌套 brace pattern 可耗尽 Node 调用栈。检查本仓库用法发现 `shadcn` 是 devDependency，页面源码只引用其 tailwind.css，没有调用该 CLI 或 braces JavaScript；最终 nginx 镜像没有 node_modules 或 Node 服务。由这些事实推断：目前未发现该模式解析器暴露在已部署 API/网页运行路径；构建/组件工具链仍保留受影响依赖，不能推广为不存在风险。npm 给出的自动方案包含 shadcn 主版本变化，不属于本任务，未执行。没有触发漏洞、容量压测或更新锁文件；后续需对实际使用的组件 CLI/构建输入评估必要处置。

## 失败保留、收尾与验收结论

除前述目录权限及第一次接入镜像锁版本失败，私有采集器还保留两次操作错误：轨迹 HTTP body 是 JSON，首次完整性汇总误把已解析 JSON 当成字节摘要；改读已保存的原响应字节后全部 8 份匹配，没有重跑 Agent 或重下载。原资源清单读取使用默认 GBK 失败；改用显式 UTF-8，只继续清单读取，没有重复执行撤销或改写原业务结果。首次失败结果、命令退出码、构建日志和诊断均保留。

本轮构建/真实路径检查及文档链接、diff 检查通过。没有修改后端/前端业务源码或测试，未重复运行其已通过的 lint、类型检查和全局迁移回放；空新库的实际 upgrade/check 及新前端构建已执行，文档检查不代替这些运行证据。

收尾前按原容器 ID/image/state/ports 及原卷名字核对，无原容器变化、无原卷缺失；未声称逐字节复查了所有原数据库。仅停止本轮新 API/Scheduler/Web/PostgreSQL/Agent，两个新 Runner 已正常停止；新容器、卷、原初始空卷、失败镜像与私有原始材料均保留，没有 down -v、清缓存或删除旧资源。实际源码与锁文件摘要、构建/启动记录、行政对象与闭环、全部下载、矩阵和生命周期原响应分别在私有目录保存，不提交秘密/日志/数据库/采集脚本。

验收状态：控制平台和接入构建问题**已最小修复并逐项检查后推送**（`284d910`、`6de27bf`，`origin/main`）；干净完整控制 Compose、按文档新环境 HTTP/MewCode 三任务闭环及上述具名权限矩阵**已验证**；真实观测正向及其详情归属、另一个真实 Agent/新环境 Python 接入、其他权限参数组合/恢复生命周期分支、真实版本改善/退化、容量及长期运行仍**待验证**。本轮没有新增仓库测试、用例、fixtures、mocks 或模拟结果，没有重做完整恢复。M4 保持部分验收。


## 2026-10-12：观测材料缺口的后续补齐

上面的 ObservedRun=0 与正向缺口保留为本轮历史事实。后续使用既有 trae Agent 的直接任务/实时被动 exporter，独立项目/来源/数据库/卷完成 3 个真实 ObservedRun、100 事件及 40 个具名权限/去重/冲突请求；API 暂停补传与真实 Web 节点核对通过，不使用主动 HTTP/SDK 事件伪造观测。最新边界及正常停止/重启见[被动观测验收](observation-trae-acceptance-20261012.md)。其他权限/接入/生命周期组合保持原缺口。
