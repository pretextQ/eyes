# 用 Eyes 接入本机 Zeta

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
  "name": "Zeta read-only agent",
  "external_version": "<commit-and-source-digest>",
  "capabilities": {
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

## 2026-10-08 实测

使用现有 `integrations/deta/coding-smoke.jsonl` 的 3 个任务及原有代码评分器，未添加或修改测试文件、用例、模拟 Agent。

| 场景 | 实际结果 |
| --- | --- |
| 正常并发 | Deta 3/3 执行成功、评分 3/3 通过；Zeta 3/3 执行成功、评分 0/3 通过 |
| 准备阶段终止一个 Zeta 工作进程 | 该尝试 failed、额度释放；其余两个 Zeta 任务与全部三个 Deta 任务继续成功执行 |
| 执行阶段终止一个 Zeta 工作进程，再取消整批 | 9 个尚未开始任务 cancelled、没有创建 Attempt；2 个已开始任务自然完成；被终止的 Zeta 尝试 unknown 并保留 1 个额度 |

正常批次的实际 `deta.run` / `zeta.run` SDK span 在同一宿主机重叠，峰值为 **Deta 1 + Zeta 2 = 3**，与项目执行额度 3 一致。不是仅根据排队数量或页面状态推断。六次正常执行的证据均为 sealed，六个评分均有有效结论。

Zeta 评分未通过符合它当前的能力：`stats.py` 保留原始错误实现，`total.py` 和 `unique.py` 未生成。模型给出修改建议不等于文件被修改。运行成功、评分通过与证据封存分别记录。

批次 ID：

- 正常：`8b35ca86-f08f-4489-9a9f-875828717132`
- 准备失败隔离：`2d057c2b-9c21-475a-9e46-0e839bd633a5`
- 执行中断与取消：`85b59bcf-2ac9-4991-92b7-4dffc3722123`

环境为 macOS Apple Silicon、CPython 3.14.7、独立 PostgreSQL 18.6 副本与 `0004_experiment_batches`，两个 Runner 使用不同令牌、状态目录和 Agent 解释器。没有更改原数据源或两个 Agent 项目的源码。两项目均有已有未提交修改，因此目标版本同时记录提交号和实际 Python 源码摘要：

- Deta：`f9b0b82d94695da440af73d94bc1424c87d371de`，源码摘要 `0d0547dc410fde8f71baa97b881a9f4f5cbf06b4d9cfeafab510a8dcdb269fa1`。
- Zeta：`0741e989f8f51c0bcec0349ce786b4366945d0e6`，源码摘要 `6825734e6829bcf13b807de2405b06ea732c8f11153f7b05b38aba7a4925d134`。

本地原始 API 结果、SDK 事件、进程中断记录、实际依赖版本、Runner 状态与配置保存在 Git 忽略的 `data/multi-agent-validation-20261008/`。`acceptance.json` 汇总结果，`concurrency-evidence.json` 保存执行区间与 SDK span。凭据文件为私有本地文件，不提交。

验证后停止本轮两个 Runner 和 scheduler，保留 API、数据库及结果供查看。隔离项目中仍有一个 unknown 预留额度；没有远端停止证据，未调用人工 resolve 释放它。

这次是两个 Python Agent 的受控本机验证，未覆盖真实 HTTP Agent、Runner 整体崩溃重启、数据库/网络故障或吞吐压测。取消场景中两个未被终止的已运行任务在 Runner 收到取消前自然完成；没有验证远端主动停止确认。三个槽位的实测不构成生产容量承诺。
