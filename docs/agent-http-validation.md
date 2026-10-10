# 统一 Agent HTTP 运行时检查记录

日期：2026-10-10，Asia/Shanghai。状态：**实现及静态检查完成，真实 HTTP 验收阻塞**。未用参考服务、模拟 Agent、预设输出或历史 Python 运行数据冒充本轮 HTTP 验收；没有修改或新增仓库测试、用例、fixtures、mocks。

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

## 未完成的真实验收

已有 API/Runner/评分器依赖 Linux/POSIX；目前 Docker Linux 引擎无法恢复，控制 API 不可达，不能运行完整链路。本轮没有创建新实验，以下都标为阻塞：

- 新目标实际发现、发布、导入现有三任务并经 Runner → HTTP → 真实 MewCode 执行。
- 原独立评分器下载已固定产物，实际功能评分及引用核对；不能沿用历史 3/3 结论。
- Eyes 与 Agent 两侧正确/缺失/错误/越权凭据检查；事件/产物下载、大小/摘要、清单与评分关联。
- 同键重放、按键查询、409 冲突、重启保持同 run_id、unknown 占额的真实行为与故障验证。
- 可选取消、资源和停止确认：MewCode 当前明确不支持取消及资源，不能用杀客户端推导远端停止；需具备这些能力的真实目标另外验证。

环境恢复后按[运行时文档](agent-http-runtime.md)和 [MewCode HTTP 接入说明](../integrations/mewcode/README.md)执行，保存新版本、命令、原始响应和失败记录到独立私有目录。M0/M1 仍未完整验收。本任务没有开展后续“重启自动协调”或“普通契约显式版本迁移”。
