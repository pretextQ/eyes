# MewCode 接入

本项目在当前 Windows／PowerShell 开发，API 与 Runner 在本机 Docker Desktop Linux 容器中运行。MewCode 源码项目为 `D:\projects\MewCode`；Eyes 根目录的 `MewCode/` 保存验证记录。

## 三份核心文件

| 文件 | 职责 |
| --- | --- |
| [README.md](README.md) | 接口、配置、启动步骤和验证边界 |
| [bridge.py](bridge.py) | prepare、execute、cleanup；调用真实 MewCode 并采集事件与轨迹 |
| [runner.example.toml](runner.example.toml) | Python Adapter 入口、解释器、路径、资源限制和独立评分器 |

这三份文件构成直接 Python 接入。统一 HTTP 接入复用同一 bridge，由 [http_service.py](http_service.py) 提供协议服务，并使用 [http-runner.example.toml](http-runner.example.toml)。Docker、发布和采集脚本是配套工具，运行记录见 [MewCode 验证目录](../../MewCode/README.md)。

## bridge 接口

- `prepare(request, context)`：把 input.files 写入独立任务目录，拒绝越界路径、目录本身和保留的 `.mewcode/` 路径。
- `execute(request, context)`：读取目标 parameters 和 `context.secrets["model"]`，创建独立 Agent、工具、会话和对话，执行真实 Agent.run。
- `cleanup(request, context)`：完成生命周期；本接入没有持久外部服务需要关闭，保留轨迹和产物供上传及评分。

业务输入如下，预期答案和评分口径不放进 prompt：

```json
{
  "prompt": "读取 stats.py 并修复 mean 函数，随后用 Python 检查。",
  "files": {
    "stats.py": "def mean(values):\n    return sum(values) / (len(values) - 1)\n"
  }
}
```

输出为带 `schema_version="1.0"` 的 ExecutionResult，保存 answer、session_id、model、input_tokens、output_tokens、loop_completed 和错误。只有收到 LoopComplete 且没有 ErrorEvent 才返回 succeeded。流式文本保存在轨迹中，其他实际模型/工具事件通过 SDK 上报；`.mewcode/eyes-trajectory.json` 上传为 `mewcode-trajectory.json`。用例要求的代码文件由 Runner 按 artifact_requirements 采集。

## 安装与配置

Linux 运行环境需要 Python 3.14+、当前 Eyes 和 MewCode。模板使用 `/app/.venv/bin/python`，Eyes/integrations 位于 `/app`，MewCode 位于 `/opt/mewcode`。按实际挂载调整解释器、import_paths 和 server_url，不能把 Windows 路径填入容器配置。

### 从干净环境构建接入镜像

先按 Eyes 根 README 启动独立控制平台。已有 `eyes-mewcode:local` 或历史脚本不代替本次构建；MewCode checkout 必须包含它自己的 `uv.lock`，先确认提交和工作区。Windows PowerShell 在 Eyes 根目录执行：

```powershell
git -C D:/projects/MewCode status --short
git -C D:/projects/MewCode rev-parse HEAD
docker build --no-cache --pull --build-context mewcode=D:/projects/MewCode -f integrations/mewcode/Dockerfile -t eyes-mewcode:independent .
docker run --rm eyes-mewcode:independent uv pip check --python /app/.venv/bin/python
```

Dockerfile 用 Eyes `uv.lock` 执行 `uv sync --frozen --no-dev`，再从 MewCode 锁文件导出非开发依赖，只安装当前 Eyes 环境缺少的包并安装 Agent 本身。共享包保持 Eyes 的冻结版本；因此组合环境不宣称逐项等于 MewCode 自己的锁文件。最后 `uv pip check` 验证组合依赖约束，失败时停止接入，不自动升级或改锁文件。模型参数和密钥只在运行时提供，不能 COPY 进镜像。

Python Runner 使用该镜像及本页模板；统一 HTTP 服务使用同一镜像，以 `uvicorn integrations.mewcode.http_service:app --factory --host 0.0.0.0 --port <Agent端口>` 启动。HTTP 服务运行时需要 `AGENT_HTTP_TOKEN`、`MEWCODE_MODEL_KEY`、`MEWCODE_HTTP_VERSION`（实际提交）、`MEWCODE_PARAMETERS_FILE`（挂载的无密钥 JSON 参数）和 `MEWCODE_HTTP_STATE`（独立可写私有状态目录）。新命名卷可挂载到镜像已创建的 `/app/data/artifacts`，将它作为 Agent 专属状态目录；不要挂载控制平台证据卷。其他挂载点应预先以运行用户 UID/GID 10001 创建并赋予 `0700`，不能让服务通过 root 或开放权限绕过写入故障。

HTTP Runner 可使用干净控制镜像，另只读挂载 `integrations` 到 `/app/integrations` 以加载既有评分器，复制 `http-runner.example.toml` 到新私有目录。配置 API 地址、Agent origin、独立 state_dir 和实际槽位；在容器内部用发现命令发布目标，详见[统一 HTTP 接入](../../docs/agent-http-runtime.md)。Runner 凭据通过单独环境文件提供；Agent 只拿 Agent/model 凭据，不挂载项目管理或 Runner 环境文件。每个 Runner 使用自己的私有状态卷。分开执行/评分时，execute 凭据配置 score_slots=0，score 凭据配置 execution_slots=0。

独立项目中读取 plugins 摘要、导入原三任务、发布评分器、创建实验及签发限定目标/工作类型的令牌后再启动 Runner；不要直接运行固定读写 `data/mewcode-integration` 的历史 publish/run 脚本。实际新环境、权限与首次失败见[本轮验收](../../docs/clean-deployment-permissions-20261011.md)。

在 Windows 创建独立运行配置：

```powershell
New-Item -ItemType Directory -Path data/mewcode-python -Force
Copy-Item integrations/mewcode/runner.example.toml data/mewcode-python/runner.toml
```

将该目录挂载到 `/app/data/mewcode-python`。它已被 Git 忽略；凭据限制本机访问权限。Runner 环境提供 EYES_RUNNER_TOKEN 和 MEWCODE_MODEL_KEY，模板只把模型密钥列入 worker 环境白名单。

发布 Python 目标时使用以下字段：

| 字段 | 配置 |
| --- | --- |
| schema_version | 顶层及 capabilities 均为 1.0 |
| external_version | 实际 MewCode commit 与源码摘要 |
| capabilities.adapter | python |
| capabilities | session_isolation=true，environment_isolation=false，cancellation/idempotency/reconciliation=false，observation=[task, sdk] |
| config.agent | mewcode，对应模板中的 python_agents.mewcode |
| config.parameters.provider | 当前真实 provider 的 name、protocol、base_url、model、thinking、context_window、max_output_tokens；不包含 api_key |
| config.parameters | permission_mode=dontAsk、max_iterations=12，按实际需求固定 |
| secret_refs.model | env:MEWCODE_MODEL_KEY |
| concurrency_limit | 1 |

接入使用 external 执行范围、并发 1。独立目录与权限检查不构成操作系统安全沙箱，停止本地进程不证明远端模型停止。直接 Python 接入没有取消、幂等和查询恢复钩子；HTTP 接入的幂等/查询由持久化协议服务提供。

## 发布与运行

先核对各实际解释器加载的 Eyes、bridge 和 scorer 源码，避免缓存镜像中的 `/app/integrations` 遮蔽新代码。在容器内读取能力与评分器摘要：

```sh
eyes-runner --config /app/data/mewcode-python/runner.toml plugins
eyes-runner --config /app/data/mewcode-python/runner.toml status
```

通过公开 API 发布目标、导入原有 `integrations/deta/coding-smoke.jsonl`，发布 plugin=deta_code 的评分器。implementation_digest 使用 plugins 输出；评分器要求 output、events、artifacts、sealed，超时 40 秒。创建实验时固定版本、并发 1、执行超时 300 秒。通用步骤见 [Agent 接入说明](../../docs/agent-integration.md)。

签发限制到该项目、目标及 execute/score 的 Runner 令牌，在容器环境提供后运行：

```sh
eyes-runner --config /app/data/mewcode-python/runner.toml run
```

每个 Runner 使用独立令牌和 state_dir。重跑创建新实验；修改桥接、参数或评分器后发布新版本，保留旧结果。配套旧脚本固定使用 data/mewcode-integration，新目录使用上述直接命令与公开 API，避免覆盖既有记录。

## 本机重启与再次评测

最新实际验证为 [2026-10-11 HTTP 记录](../../MewCode/2026-10-11-rerun/REPORT.md)：API 18060、Agent 19050、Web 18082、PostgreSQL 55440，私有配置位于 MewCode/2026-10-11-rerun/private。此环境使用 http-runner 配置，与上面的 Python 模板分别运行。

数据库按该次私有部署配置启动后，在 PowerShell 启动本次已有容器：

```powershell
docker start eyes-mewcode-rerun-api eyes-mewcode-rerun-agent
```

确认 `/health/ready` 为 200。需要新实验时再启动 eyes-mewcode-rerun-scheduler 和 eyes-mewcode-rerun-runner，以该项目 manage 身份创建关联实验，每次另建记录子目录。Web 设置 EYES_API_PROXY_TARGET 指向本次 API，启动方式见 [前端说明](../../docs/frontend.md)。

## 验证边界

[最新 HTTP 记录](../../MewCode/2026-10-11-rerun/REPORT.md)实际通过 3/3 执行、3/3 独立评分与 12/12 功能检查，并保留首次缓存安装不一致的 unknown。此前直接 Python 基础闭环见 [Windows/MewCode 记录](../../docs/mewcode-validation.md)。

本次整理三份接入文件不新增验收结论。完整告警服务、扩展工具、复杂仓库能力、安全隔离、活动崩溃恢复、双 Agent 并发及容量仍需相应验收。
