# 统一 Agent HTTP 运行时检查记录

日期：2026-10-10，Asia/Shanghai。状态：**实现与静态检查完成，Docker 恢复后的真实 MewCode HTTP 基本闭环验收通过**。下方保留首次阻塞与失败事实，续验收结果在末节。参考服务实际调用 MewCode，没有模拟 Agent、预设输出或沿用历史 Python 结果；没有修改或新增仓库测试、用例、fixtures、mocks。

## 版本与范围

- Eyes 编辑基线：`390dd11eea7eaab8653fbc29738289c068a551e3`，版本 0.1.0；本记录随运行时实现独立提交，交付提交可通过 `git log -1 --format='%H %s' -- docs/agent-http-validation.md` 定位。
- 检查环境：Windows、CPython 3.14.4、uv 0.11.7、Ruff 0.16.10；使用已有 `.venv`，本次没有安装依赖或改变锁文件。
- 拟验收目标：已有真实 MewCode，源码 HEAD 为 `3f104082b6c5ca53efe273630bf08f67f1fc3ff5`（本次只核对版本，未修改核心源码，未声称运行版本已冻结）。沿用已有私有模型配置及原 `integrations/deta/coding-smoke.jsonl` / `scorer.py`。
- 新增 `agent_http` 客户端、统一发现发布、接入端持久化外壳及实际 MewCode 回调；旧 HTTP/Python 不变。外部协议模型和 Schema 未改，平台数据库不迁移，历史实验/评分/运行目录未改。

## 实际命令与结果

以下命令在仓库根目录执行。首次新文件规范检查报告长行，随后 Ruff 格式化后重新检查通过；没有将首次失败隐去。

| 实际命令 | 结果及限制 |
| --- | --- |
| `.venv/Scripts/ruff.exe check src migrations integrations/mewcode/http_service.py` | `All checks passed!`；代码规范检查 |
| `.venv/Scripts/ruff.exe format --check src migrations integrations/mewcode/http_service.py` | `74 files already formatted` |
| `.venv/Scripts/python.exe -m compileall -q src/eyes integrations/mewcode/http_service.py` | 退出 0；字节编译，不执行 Agent/Runner |
| `.venv/Scripts/python.exe -m eyes.adapters.agent_http --help` | 退出 0，发现命令参数可载入；未请求真实目标 |
| `git ls-files '*test*' '*spec*'` | 没有已跟踪测试文件；仓库未提供可运行的相关测试套件，未新建测试 |
| `docker ps --format '{{.Names}} {{.Ports}}'` | 初次失败：无法连接 `dockerDesktopLinuxEngine`，管道不存在；启动 Desktop 后查询未响应 |
| `Start-Process .../Docker Desktop.exe -WindowStyle Hidden` | 已尝试启动；不能证明引擎就绪 |
| `Start-Service com.docker.service` | 失败：当前权限无法打开该系统服务；未提权、未更改系统设置 |
| `docker desktop status` / `docker desktop start` | 前者无法读取状态；后者没有完成启动，不能计为成功 |
| `Test-NetConnection -ComputerName 127.0.0.1 -Port 18044 -InformationLevel Quiet` | False，原 Eyes 控制 API 未开放 |

定向查看 Docker backend 日志发现：`starting services: initializing Inference manager`，监听 `dockerInference` 时出现 `The file cannot be accessed by the system` / 文件名、目录名或卷标语法错误，backend 随后崩溃。未重置 Docker、删除存储或安装替代系统。长时间不响应的本轮查询已停止，保留失败事实。

已确认原私有模型配置文件存在；没有输出模型密钥、管理/Runner 令牌或提交私有运行数据。文件存在不代表提供方认证成功，本次未运行模型请求。

## 首次未完成的真实验收（后续已解除环境阻塞）

已有 API/Runner/评分器依赖 Linux/POSIX；目前 Docker Linux 引擎无法恢复，控制 API 不可达，不能运行完整链路。本轮没有创建新实验，以下都标为阻塞：

- 新目标实际发现、发布、导入现有三任务并经 Runner → HTTP → 真实 MewCode 执行。
- 原独立评分器下载已固定产物，实际功能评分及引用核对；不能沿用历史 3/3 结论。
- Eyes 与 Agent 两侧正确/缺失/错误/越权凭据检查；事件/产物下载、大小/摘要、清单与评分关联。
- 同键重放、按键查询、409 冲突、重启保持同 run_id、unknown 占额的真实行为与故障验证。
- 可选取消、资源和停止确认：MewCode 当前明确不支持取消及资源，不能用杀客户端推导远端停止；需具备这些能力的真实目标另外验证。

环境恢复后按[运行时文档](agent-http-runtime.md)和 [MewCode HTTP 接入说明](../integrations/mewcode/README.md)执行，保存新版本、命令、原始响应和失败记录到独立私有目录。M0/M1 仍未完整验收。本任务没有开展后续“重启自动协调”或“普通契约显式版本迁移”。

## Docker 恢复后的真实验收

用户明确要求检查已修复的 Docker 并继续本任务。2026-10-10（Asia/Shanghai；实际执行开始约 21:16）经实际 HTTP 完成：导入原任务 → Runner → 统一 HTTP 服务 → 真实 MewCode/DeepSeek → 文件与命令工具 → 外部事件/产物 → Eyes 证据 → 原独立评分进程 → 公共 API 查询和认证核对。没有修改 MewCode 核心、协议模型、Schema、数据库迁移、任务或评分器代码。

### 版本和拓扑

- Eyes：`6473c962d65255c83e4265fea12f6afce2f4932c`，0.1.0；源码集合摘要 `9d89c85c8bfc48ed0b12406fb37d89c17d332a1342e50b62efdcbfa9cb90a16b`。Agent/API/Scheduler 绑定本轮源码，Runner 的安装包内容经比对与同版本 68 个源码文件一致。
- MewCode：`3f104082b6c5ca53efe273630bf08f67f1fc3ff5`，源码集合摘要 `a007cfa9bcfb9d2f1051a154c6f64d2b42542fc83061d45ba046787d0b94e35d`；真实容器内文件逐项匹配。HTTP 回调摘要 `10bbc929bd3cb08f8818313f5ceef76982f33e5bbf5986882cea5a6becf8cd1c`。
- 原数据集摘要 `9e868ae0c53f1e2f88d6114b5c76e591647ecd78ef6b6d3882cbaf8b49771e4b`；原独立评分器摘要 `11badc0d2397a20b51d7c41fcdbb246b68ca2dca600646b2a6f95ccd234a89b6`。没有新增评测用例。
- Docker Engine 29.4.2；已有缓存镜像 `sha256:420dba75f4b41b95976e91e0d590cfc9d1fb3397a8a64b39c1c21ed167ceca2a`，Linux CPython 3.14.7。实际依赖通过 `uv pip freeze --python /app/.venv/bin/python` 保存，不宣称复用了完整 Eyes 锁文件，本次没有安装依赖。
- 原专用 Windows PostgreSQL 15.17：127.0.0.1:55435；新控制 API `eyes-agent-http-api`：127.0.0.1:18046，readiness 200，head=`0004_experiment_batches`；新 Scheduler `eyes-agent-http-scheduler`。
- HTTP Agent `eyes-agent-http-mewcode`：127.0.0.1:19045，独立接入端状态卷；Runner `eyes-agent-http-runner` 与 Agent 共享网络 namespace，通过 loopback HTTP 调用。Runner 注册仅有 http/agent_http，python_agents 为空，业务没有走 Python Adapter；Python 仅用于接入服务回调和独立评分器。
- provider 沿用私有配置：DeepSeek、deepseek-flash、thinking=false、context_window=128000、max_output_tokens=8192、最多 12 轮、permission_mode=dontAsk；并发 1，执行截止 300 秒、评分截止 40 秒、证据等待 15 秒。远端模型别名不等同于固定权重。

### 新身份与结果

TargetVersion=`ed67629b-400c-43cc-950f-b2b228384823`，DatasetVersion=`eef0b51b-0bc9-4562-b60d-a5d580ed9dd1`，ScorerVersion=`c7cdb40c-adbb-4cea-a386-a5fe406c7249`。

最终实验 **`e93b6f02-0d9e-4a0d-abba-47e48e305847`**，关联首次失败实验 `e0bc311d-a3b5-41fe-a879-1edc6d6ca422`，没有覆盖原实验。计划/成功/有效评分/通过均为 3，最终实验失败与 unknown 尝试均为 0、未解决评分为 0。每项运行一次。

| 原任务 | Attempt | 外部 run_id | 执行耗时（秒） | 独立功能检查 | Eyes / 外部事件 | 产物 |
| --- | --- | --- | --- | --- | --- | --- |
| fix-mean | `2fd903ab-9166-4fbb-86aa-dd4db8f7333a` | `7e70eb2f-ea84-4fdc-80ae-63c8259e8a24` | 8.982 | 4/4 pass | 24 / 20 | 3 |
| integer-cli | `c1683190-ebe0-49d6-bb86-59f1516230b6` | `4d41cef7-300c-43c8-bacf-4cd271b8c00b` | 5.664 | 4/4 pass | 20 / 16 | 2 |
| stable-unique | `b56ffdfd-983d-414b-8fb4-71eb2e08b6f9` | `ca744d44-08b0-4a49-a7b1-be26e61398ee` | 7.736 | 4/4 pass | 16 / 12 | 3 |

耗时为本次 Eyes execution_intent_at 到 finished_at，包括轮询和上报，不代表纯模型延迟或容量。共有 60 条 Eyes 事件，其中 48 条 `agent.event`/source=target_trace；三个运行的外部事件身份、顺序及内容全部匹配。8 份产物包括三个代码文件、三份真实轨迹及两个由实际 Python 工具执行产生的 pyc；两侧下载字节、大小、SHA-256 全部一致。

三个结果均 stopped_confirmed=true、cleanup=succeeded、sealed、reported dropped_events=0。sealed 仅覆盖所声明事件边界。三个 ScoreRun 均有独立 trace，绑定准确的冻结 Manifest，评分引用全部属于该授权证据视图。评分实际运行下载的冻结代码，每项四个功能检查；不是读取 Agent 自述。代码范围、解释质量、复杂仓库任务及稳定性不在这 12 项检查中。

### 实际协议与认证核对

- 合法发现、按键查询、状态和结果均 200。同键原参数重放返回 200 和相同 run_id/快照；同键更改 task_id 返回 409/idempotency_conflict，同 attempt 更换键返回 409/attempt_conflict，不产生新业务执行。
- 在所有任务完成、Runner 停止后实际 `docker restart eyes-agent-http-mewcode`。三个原 run_id 的完整快照保持相同，按键/结果/重放仍 200；不是重启正在执行的任务或 Runner 崩溃验收。重启前后原始响应与比较分别保存。
- 另以只读方式核对外部协议存储：始终为 3 个运行、48 条事件、8 份产物、0 输入资源，重放与冲突未新增业务运行；平台证据和评分仍通过认证公开 API 查询，Runner 没有连接控制数据库。
- Agent 的发现、提交、按键/状态/结果、事件和产物端点缺失/错误凭据均 401/unauthenticated；Eyes Runner 令牌不能作为 Agent 令牌使用。Eyes 缺失/错误/Agent 凭据访问结果为 401。
- Eyes read 身份读取结果、事件、清单与产物成功，发布目标返回 403/permission_denied；Runner 读取管理结果为 403，当前目标授权产物为 200，旧 Python 目标的 Runner 读取新 HTTP 产物为 403/artifact_scope。
- MewCode 声明 cancellation=false/resources=false，真实调用这两个端点均返回 422/unsupported_capability。没有用伪造停止或模拟文件验收可选能力的正向路径。
- Runner outbox pending/rejected/orphaned 均为 0；保留三个独立评分目录及首次部署失败的三个隔离目录。没有因最终成功删除首次失败记录。

### 实际命令、私有记录与失败

部署使用原 pg_ctl 启动命令，分别 `docker run` 上述三个服务和 Runner。核心命令：`python -m eyes.adapters.agent_http ... --token-env AGENT_HTTP_TOKEN`、`eyes-runner --config /run/runner.toml plugins/run/status`、`eyes-admin issue-token`、管理 API POST targets/scorers/datasets/import/experiments，以及公开 GET results/case-runs/attempts/events/manifests/artifact content。原始请求响应通过本机私有 `data/mewcode-http/publish.py`、`status.py`、`collect.py`、`protocol_requests.py`、`final_facts.py` 采集；这些是实际部署/证据操作，不是新增仓库测试、用例或 mocks，目录未提交。

保留的私有文件包括 versions/source-check/installed-source-check、plugins/published/experiment/results/case-runs、acceptance、两侧 evidence 与 artifact-verification、score-input/score-evidence-link、协议重启前后响应、restart-comparison、runner-status、实际依赖及组件日志。目录 Windows ACL 只授予当前用户，Agent 只挂载自己的状态子目录及模型参数，未挂载 Eyes 管理/Runner 凭据。证据文件按本次已解析模型/Agent/read/manage/Runner 密钥字面值检查无匹配；这不构成对任意秘密的完整识别保证。私有原始数据、凭据和产物均未提交。

失败记录：

1. 首次实验三项准备失败：Supervisor 的 PYTHONPATH 覆盖没有传给隔离子进程，旧缓存镜像内安装仍为旧 Eyes，worker exited without a response。保持子进程环境隔离规则，使用 `docker cp src/eyes/. ...:/app/.venv/lib/python3.14/site-packages/eyes` 同步完整安装代码，核对 68 个文件一致后创建关联新实验；没有改核心运行时来传播平台环境变量。
2. Windows 采集器最初使用 GBK 写入真实输出，出现 UnicodeEncodeError；改用 UTF-8 后重新经 API 采集。采集器还曾将公开事件/用例的 record 包装当作原协议内容，引发 KeyError，按 content 结构修正后重新采集，未改远端结果。
3. 镜像没有 pip，`python -m pip freeze` 失败，改用已有 uv 命令成功保存依赖。
4. Agent 重启后过早查询出现 RemoteProtocolError；等待服务实际就绪后重新查询并保存新响应。早先复制的旧响应没有用于最终重启判定。

### 当前边界

本任务要求的真实 MewCode HTTP 导入、执行、独立评分、证据查询与基础认证已完成，不再受 Docker 阻塞。采用可信本机部署，参考服务存储为外部协议 SQLite，控制端始终为 PostgreSQL；同一镜像包含接入源码，不构成不可访问评分材料的强沙箱。本次证明 HTTP 任务不传预期/评分/Eyes 凭据，不能推广为对抗性隔离保证。

本次仅同步验收文档，无产品代码变更；`git diff --check` 通过，修改文档的 85 个本地链接均存在。源码静态检查见前述实际命令，真实运行使用同一已检查源码；没有通过新增仓库测试来替代验收。

取消确认/资源上传正向流程、响应丢失故障注入、活动任务崩溃/unknown 恢复、多个真实统一协议实现、跨项目完整权限矩阵、干净部署及容量仍待验证；不宣称 M0～M4 全部验收。本轮没有开始后续自动协调或普通版本迁移任务。验收结束后本轮 Runner 保持停止，API/Agent/Scheduler 和专用 PostgreSQL 保留运行供查询。
