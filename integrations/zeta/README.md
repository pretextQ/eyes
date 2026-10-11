# 用 Eyes 接入本机 Zeta

> 当前仅在 Windows／PowerShell 开发，API/Runner 在本机 Linux 容器运行。下文 `sh` 与 POSIX 路径示例仅适用于容器内部；Zeta 在当前 Windows 环境尚需重新验收，启动方式参考 [Windows/MewCode 说明](../mewcode/README.md)。

`bridge.py` 调用真实 `zeta.app.run_agent`、`HookRuntime` 和 Agent loop，通过 DeepSeek 请求模型，并转发生命周期事件、保存消息与工具结果。没有修改 Zeta 源码，也没有把模型回答写成代码文件来替代 Agent 的工具能力。

当前 Zeta 只有工作区内的 `read` 工具。每项任务拥有独立 Runtime、模型客户端、工作目录和轨迹；此版本可声明会话及环境隔离并配置并发 2。这个声明仅适用于当前只读工具与无共享业务状态的模型调用；以后加入 shell、写工具或共享服务时需要重新评估。独立目录不是操作系统安全沙箱。

绑定保持 `execution_scope = "external"`、`cancellation = false`：停止本地进程或关闭请求不能证明远端模型生成已经停止，异常中断可能成为 unknown 并保留额度。桥接支持本地协作取消，但不把它声明为远端停止保证。

## 安装与配置

Deta 与 Zeta 当前分别锁定 `langchain-openai==1.6.6` 和 `==1.6.2`，使用独立解释器。Runner 可以在同一控制端为不同目标启动不同 Python 环境。

在 Eyes 根目录准备 Zeta 接入环境：

```sh
uv venv data/zeta-integration/venv --python 3.14
uv pip install --python data/zeta-integration/venv/bin/python -e . -e ../Zeta
cp integrations/zeta/runner.example.toml data/zeta-integration/runner.toml
```

按本机路径修改示例中的 `python`、`import_paths`、`server_url`。组合环境满足两个项目的依赖约束；这不等同于复用了两个项目各自的完整锁文件。运行时应保存实际依赖列表和源码摘要。

通过公开 API 发布如下目标，版本字段填写实际源码版本；使用本机管理令牌，不把密钥明文写入目标：

```json
{
  "schema_version": "1.0",
  "name": "Zeta read-only agent",
  "external_version": "<commit-and-source-digest>",
  "capabilities": {
    "schema_version": "1.0",
    "adapter": "python",
    "session_isolation": true,
    "environment_isolation": true,
    "cancellation": false,
    "idempotency": false,
    "reconciliation": false,
    "observation": ["task", "sdk"]
  },
  "config": {
    "agent": "zeta",
    "parameters": {
      "model": "deepseek-flash",
      "base_url": "https://api.deepseek.com"
    }
  },
  "secret_refs": {"model": "env:OPENAI_API_KEY"},
  "concurrency_limit": 2
}
```

桥接面向当前 DeepSeek 接入并关闭 thinking；每任务最多 8 次模型请求、16 次工具调用、240 秒，且受 Eyes 剩余截止时间约束。输入使用 `prompt` 和可选的 `files` 映射，后者在准备阶段写入任务目录。已有数据集的 `artifact_requirements` 仍由 Eyes 采集；没有生成的文件记录缺失。

签发限制到该目标版本的 Runner 令牌，通过 `EYES_RUNNER_TOKEN` 提供；模型密钥由 `OPENAI_API_KEY` 提供。然后运行：

```sh
uv run eyes-runner --config data/zeta-integration/runner.toml plugins
uv run eyes-runner --config data/zeta-integration/runner.toml run
```

示例默认提供内置 rules 评分器。复用 Deta 的冻结代码评分器时，另添加 `python_scorers.deta_code` 绑定，使用 Deta 现有评分环境及 `integrations/deta/scorer.py`；根据 `plugins` 输出发布对应摘要的评分器。
