# MewCode 单 Agent 真实评测接入

2026-10-09（Asia/Shanghai）在 Windows 宿主机完成真实闭环：独立 PostgreSQL → Eyes API/Scheduler → Linux Runner → MewCode Agent → DeepSeek → 文件/命令工具 → 产物上传 → 原有独立评分器 → Web。没有修改 MewCode 核心源码、Eyes 核心源码、仓库测试或评测用例，没有 Git 提交或推送。

最终实验：`087a0f7c-bfd5-44d0-b27c-d812fc45cbd9`。执行成功 3/3，有效评分 3/3，通过 3/3；证据 sealed 3/3，清理成功 3/3。每项原有 4 个验收检查通过。详见 [本机验证记录](../../docs/mewcode-validation.md)。

## 接口选择

检查了 MewCode 的 `MEWCODE.md`、README、Windows/权限说明、配置加载、`__main__.py`、Agent、工具及 service 接口。

- `mewcode -p ... --output-format json --config ...` 是真实无头 CLI；JSON 输出包含结果、usage、工具计数及 session ID。内部使用 `Agent.run_to_completion`，callback 没有完整工具结果。
- `mewcode serve` 提供 `/webhook/manual`、`/webhook/alert`、`/jobs`、报告及健康接口，围绕告警、git worktree、验证、PR/CI 组织，不直接匹配 Eyes 现有 HTTP 任务契约。当前 `serve --config` 路径还在 `_serve` 内重新调用默认配置发现；本轮没有使用或修改这条路径。
- 本轮采用已有 Python Adapter，直接调用 MewCode 的真实 `Agent.run(ConversationManager)` 事件流，保留模型 usage、工具参数/结果、回合和循环结束事实。不是启动 TUI，也不是调用完整告警服务。六个默认工具为 ReadFile、WriteFile、EditFile、Bash、Glob、Grep；禁用的扩展能力没有注册，包括 MCP、team、子 Agent、自动记忆和 hooks。这些边界影响可比性，不能把结果推广到完整 MewCode 服务。
- 复用 `integrations/deta/coding-smoke.jsonl` 和 `integrations/deta/scorer.py`，没有复制评分逻辑或建立第二套 HTTP 接入。`docs/agent-protocol.md` 的统一协议仍未进入 Eyes 运行时，本轮没有宣称完成迁移。

## 配置与秘密

`prepare_local.py` 读取已有 `D:\projects\MewCode\.mewcode\config.yaml`，选用已有 `openai-compat` provider。本轮为 `https://api.deepseek.com`、`deepseek-flash`、thinking=false、context_window=128000、max_output_tokens=8192。保留这些配置，权限模式显式使用 `dontAsk`、最多 12 次迭代，Eyes 截止 300 秒。`dontAsk` 仍经过 MewCode 危险命令检测和文件路径检查；shell 不是安全沙箱。

密钥仅存 Git 忽略的本机 `model.env`，发布快照仅引用 `env:MEWCODE_MODEL_KEY`。管理/Runner 凭据与模型密钥分开，Runner 仅授权本轮目标及 execute/score。Runner 子进程环境不继承平台令牌。轨迹对已解析密钥的字面值和已知敏感字段脱敏；代码产物本身不自动脱敏。可信 shell 与同一 Runner 容器可访问容器挂载内容，不能视为凭据的安全隔离；不接入不可信任务。

私有配置位于 `data/mewcode-integration/`，Windows ACL 取消继承并只授予当前用户。不要输出、提交或分享整个目录。模型列表验证返回 200 且包含配置模型；没有把模型别名当作固定远端权重版本。

## 实际运行拓扑

| 组件 | 实际环境/地址 |
| --- | --- |
| PostgreSQL | Windows PostgreSQL 15.17，独立数据目录，127.0.0.1:55435 |
| API | `eyes-mewcode-api` Linux 容器，127.0.0.1:18044 |
| Scheduler | Windows CPython 3.14.4 独立进程，同一数据库配置 |
| Runner / Agent / scorer | `eyes-mewcode-runner` Linux 容器，CPython 3.14.7 |
| Web | Node 22.14.0/Vite，127.0.0.1:18081，代理 API |

Runner 的 fcntl、resource、POSIX 进程组以及原评分器的 killpg 使其不能原生运行在 Windows。API 产物存储也使用目录 fsync，原生 Windows 实测失败，最终使用 Linux API。原有 Windows PostgreSQL 服务保持运行，本轮使用单独 initdb 实例，不修改其数据库。

两个 Python 3.14 官方 Docker 镜像和 PostgreSQL 18.6 的拉取发生短读 EOF；最终 Dockerfile 从本机缓存的 Python 3.12 基础镜像通过 uv 安装 CPython 3.14.7，并创建 `/app/.venv`。执行进程实际为 3.14.7，未降低项目要求。Eyes 锁定环境因清华镜像 403 未成功安装；组合环境用官方 PyPI 按两项目约束解析，实际环境冻结在 `linux-dependencies.txt` 和 `windows-dependencies.txt`，不宣称等于两个项目原锁文件。发布后不要重新构建移动依赖并冒充相同环境；实际镜像 ID 已保存。

`compose.yaml` 是对 Eyes 原部署文件的构建/完整容器部署覆盖示例，已校验配置并用于构建；本轮完整 Compose 启动因镜像拉取失败，不能把它记为全栈 Compose 部署验收。实际服务按上述混合拓扑运行。

## 本机重启与再次评测

当前所有组件均保留运行。若已停止，在 Eyes 根目录按需执行以下命令。先确认没有同名进程，避免重复启动 Scheduler 或 Web。

```powershell
# 独立数据库；路径对应本轮机器，不连接其他 PostgreSQL 数据目录。
& 'D:\software\tools\postgreSQL\15\bin\pg_ctl.exe' -D 'D:\projects\eyes\data\mewcode-integration\postgres' -l 'D:\projects\eyes\data\mewcode-integration\postgres.log' -o '-h 127.0.0.1 -p 55435' -w start
docker start eyes-mewcode-api
.venv\Scripts\python.exe integrations\mewcode\local_service.py scheduler
.venv\Scripts\python.exe integrations\mewcode\local_service.py web
docker start eyes-mewcode-runner
```

Scheduler/Web 是长运行命令，分别在终端执行或用 `Start-Process -WindowStyle Hidden` 启动并重定向日志。API readiness：`http://127.0.0.1:18044/health/ready`。

浏览器刷新会丢失内存中的项目令牌。可在本机复制已有项目管理令牌，再粘贴到连接设置；不要复制模型密钥：

```powershell
(Get-Content data/mewcode-integration/manage.json -Raw | ConvertFrom-Json).token | Set-Clipboard
```

再次运行同一配置，在最终实验详情选择“关联重跑”；这会创建新的真实业务执行，保留旧结果。`publish.py` 使用持久化请求键恢复同一次发布/创建，本地存在 `published.json` 时复用已发布版本；它不是变更桥接/配置后发布新版本的工具。变更后需准备新的状态目录、版本、镜像和目标范围凭据，不能直接覆盖既有版本证据。

采集已有实验的原始记录：

```powershell
.venv\Scripts\python.exe integrations\mewcode\collect.py
.venv\Scripts\python.exe integrations\mewcode\summarize.py
```

`collect.py` 从公开 API 下载结果、事件、清单及产物，用保留的 Runner 评分输入元数据核对产物 SHA-256/大小。评分输入来源为该 Runner 曾获授权的冻结视图，不是控制端数据库直读。评分 trace/payload 已保留，正常执行目录已回收。

## 能力声明

每次执行具有独立 Agent 实例、session ID、工作目录和对话；session_isolation=true，environment_isolation=false，并发=1。容器没有 Docker socket、MewCode 私有配置或宿主源码挂载，但 API/Runner/评分共用运行环境且有网络与可信 shell 权限；独立目录不构成 OS 安全沙箱，也没有完成对抗性隔离验收。

execution_scope=external；取消、目标幂等、远端查询与恢复均为 false。停止本地进程不证明远端模型停止。Eyes outbox 重传不等于 MewCode 业务去重，模型调用失败后的 Agent 内部重试也不能保证远端请求只执行一次。本轮没有验证取消、Runner 整体重启、故障恢复、版本回归或容量；不从本轮 incidental 产物重传推广恢复承诺。

sealed 表示明确声明的 SDK/Runner 采集边界封存。轨迹包含流式文本、真实模型/工具事件和对话，不包含全部内部状态、完整提供方 HTTP 报文或远端思考过程。原评分器只覆盖冻结代码的 12 项功能检查，不完整检查指令遵循、输入不可变、文件变更范围或解释质量。

## 2026-10-10：统一 HTTP 接入（已实现，真实运行阻塞）

新增 `http_service.py`，以 `eyes.agent_service.http.create_app` 接入持久化协议服务，回调复用本目录 `bridge.prepare/execute/cleanup` 的真实 MewCode Agent 事件循环。没有修改 MewCode 核心，没有复制或修改原三任务和独立评分器。旧 Python 接入和上述 2026-10-09 历史记录保持原样；该历史 3/3 不是 HTTP 路径结果。

HTTP 目标只接收 `prompt` / 可选 `files` 业务输入和统一身份。provider、模型密钥、权限和迭代配置由接入服务本机加载；Eyes 的预期、评分配置及 Runner/管理令牌不发送给 MewCode。模型/工具原始事件由 `custom.mewcode.*` 封装，代码文件和真实轨迹作为外部产物持久化，Runner 校验后上传内部证据，由原 `integrations/deta/scorer.py` 独立执行冻结代码。

能力保持会话隔离=true、环境隔离=false、并发=1、取消=false、输入资源=false；代码准备使用 input.files。新增的幂等与按键/状态查询由 HTTP 接入端持久化映射提供，不代表模型提供方幂等或自动重放 MewCode。服务重启后不确定业务记录为 unknown，保留容量；截止时间中断不声明远端模型停止。工作目录与原始协议记录保留在新的私有 `data/mewcode-http/`，不能用原 `publish.py` 覆盖历史发布和运行记录。

以下是环境恢复后的步骤，**本轮没有实际运行这些服务或完成验收**：

1. 恢复原 Linux Eyes API（18044）、PostgreSQL 与 Scheduler，确认 readiness。使用含本轮 Eyes 源码的 Linux 环境及已安装真实 MewCode 的环境。现有 Dockerfile 可构建该环境，但需保存实际镜像 ID/依赖版本，不能把移动镜像标签当作版本。
2. 新建私有 `data/mewcode-http/`，配置独立随机 `AGENT_HTTP_TOKEN`（至少 32 字符，写入私有 agent.env）。沿用原 `data/mewcode-integration/model.env` 和 `parameters.json`，不输出或复制模型密钥进目标 JSON。环境变量 `MEWCODE_HTTP_STATE` 指向新的接入端目录，`MEWCODE_PARAMETERS_FILE` 指向已有参数文件，`MEWCODE_HTTP_VERSION` 填本次真实 MewCode commit/源码摘要及桥接版本。
3. 在 Agent 的 Linux 环境加载模型与 Agent 凭据后运行：

   ```sh
   uvicorn integrations.mewcode.http_service:app --factory \
     --host 0.0.0.0 --port 19045 --workers 1 --no-access-log
   ```

   loopback HTTP 模式下，将 Runner 与 Agent 放在同一 Linux 主机或同一容器网络 namespace（Docker 的 `--network container:<agent-container>`），使 Runner 使用 `http://127.0.0.1:19045`。不把 host.docker.internal 明文 HTTP 作为远程安全认证路径。独立远端部署必须配置 HTTPS。参考服务单进程并锁定独立状态卷，模型凭据只提供给 Agent，Runner 只取得 Agent Bearer 凭据。
4. 从该 Runner 环境执行 `python -m eyes.adapters.agent_http http://127.0.0.1:19045 --name 'MewCode unified HTTP' --token-env AGENT_HTTP_TOKEN`，保存新 target.json 后通过管理 API `/v1/targets` 发布；不能沿用旧 Python TargetVersion。复制 `http-runner.example.toml`，调整实际路径，执行 `eyes-runner --config ... plugins` 保存当前评分器摘要。通过原 API 发布评分器，仍为 `deta_code`，required_evidence 仍为 output/events/artifacts/sealed，timeout=40。
5. 使用 `eyes --url http://127.0.0.1:18044 import-dataset --name 'Existing coding smoke HTTP' --file integrations/deta/coding-smoke.jsonl` 导入原数据集。`EYES_TOKEN` 仅是管理身份。创建新的 experiment.json，填写新目标/数据集/评分器 UUID、concurrency=1、timeout_seconds=300、evidence_wait_seconds=15，再运行 `eyes --url http://127.0.0.1:18044 create --file ... --key <本轮持久化请求键>`。保存新实验身份到独立目录。
6. 使用控制端 `eyes-admin issue-token --project-id ... --role runner --target-id ... --work-kind execute --work-kind score` 签发新目标范围凭据，保存为私有 Runner 凭据；不要将旧 Runner 的授权范围强行扩展。Runner 环境加载 `EYES_RUNNER_TOKEN`，运行 `eyes-runner --config ... run`。HTTP Runner 配置没有 Python Agent 绑定，实际业务必须经过协议 HTTP 接口。
7. 经公开 API 获取新实验 results、case-runs、attempts、events、manifests、score-runs 及 artifact content，保存原始响应与字节摘要，核对评分引用。另核对 Agent 提交/按键查询/状态/结果/事件/产物的认证、同键重放与冲突；独立评分必须实际执行，不能只核对 Agent 自述。保持原历史文件不变，原 `collect.py` 固定写旧目录，本轮应在新目录按相同公开端点采集。

本轮阻塞证据：Docker Desktop 4.72.0 在 Inference manager 的 dockerInference listener 初始化时报文件访问/路径语法错误并崩溃；启动系统服务权限不足，原 API 不可达。因此导入、真实 HTTP 执行、独立评分、证据查询和两侧认证均未验收，详见[运行时检查记录](../../docs/agent-http-validation.md)。可选取消/资源需其他实际支持目标补证据。
