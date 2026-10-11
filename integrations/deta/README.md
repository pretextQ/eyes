# Deta 接入组件

当前仅在 Windows／PowerShell 开发，API/Runner 在本机 Linux 容器运行。启动方式见 [Windows/MewCode 说明](../mewcode/README.md)，通用流程见 [Agent 接入文档](../../docs/agent-integration.md)。Deta 在当前 Windows 环境的接入仍需重新验收。

本目录保留以下接入组件：

- `bridge.py`：准备任务文件、调用 Deta，并转发生命周期事件及采集轨迹和产物。
- `scorer.py`：在独立进程中执行冻结代码并返回评分结果。
- `coding-smoke.jsonl`：三个编码任务及评分预期。
- `publish.py`：发布目标、测试集和评分器配置。
- `run_runner.py`：启动配置好的 Runner。

使用时需在本机 Linux 容器内安装 Eyes 与 Deta，按实际路径、解释器、网络及依赖配置接入。模型密钥通过环境变量提供，目标版本仅保存密钥引用；项目管理令牌和 Runner 令牌分别授权。多个 Runner 使用独立凭据及状态目录。

代码和数据集的保留不代表当前环境已完成执行、评分、取消、恢复或并发验收。
