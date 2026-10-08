# 用 Eyes 评测 Deta coding agent

2026-10-03（Asia/Shanghai）完成一次真实模型端到端运行：Eyes API → PostgreSQL 调度 → 宿主机 Runner → Deta `AgentSession` → DeepSeek → 文件工具 → 证据上传 → 独立 Python 评分 → Web 展示。没有修改 Deta 的核心源码，也没有修改 Eyes 的公共协议。

## 本轮结果

实验 ID：`0c84eb9f-86f5-490e-aab8-d624c0713462`。

| 任务 | 验收内容 | 结果 | 执行耗时 | 模型响应 / 工具调用 |
| --- | --- | --- | --- | --- |
| fix-mean | 普通序列、单元素、负数、空序列异常 | 4/4，通过 | 7.45 秒 | 4 / 4 |
| stable-unique | 顺序去重、空输入、字符串、不可哈希列表 | 4/4，通过 | 9.76 秒 | 6 / 6 |
| integer-cli | 正数、负数、无参数、大整数 JSON 输出 | 4/4，通过 | 7.41 秒 | 5 / 4 |

计划运行 3、成功 3、有效评分 3、通过 3、失败尝试 0、未知尝试 0、未解决评分 0。每个任务执行一次、并发为 1。耗时取 Eyes 执行意图至结果提交时间，不包含排队和评分。

轨迹包含 15 次有 usage 的模型响应和 14 次工具调用，覆盖 `read`、`edit`、`write`、`bash`。提供方 usage 累计 total_tokens 为 38,446（包含各轮重复上下文，不等于独立文本量或费用）。每个任务保存代码、Deta 轨迹、Deta span 三份产物，共 9 份；Eyes 清单收录 94 条事件，三次执行均为 sealed，报告 dropped/capture/truncated 为 0。sealed 只覆盖桥接声明的采集范围。

评分执行从 Eyes 下载的已冻结代码，验收输入保存在 dataset expectations，不提供给 Deta。判定依赖真实函数返回值、异常类型、CLI JSON 与退出码，不依赖 Agent 自述。自然语言解释不在此评分口径内：`fix-mean` 的回答把原公式对 `[1,2,3]` 的结果写成 `1.5`，实际上为 `3`；代码正确不代表说明全部正确。输入不被修改、严格文件变更范围等要求也未全部纳入独立验收，不能按这 12 项检查宣称完整遵循所有指令。

## 版本与运行配置

- Eyes 基线：`66daae27dcdf9541413e55d6fbbceaaf6621050e`，外加本目录接入代码。
- Deta：`f9b0b82d94695da440af73d94bc1424c87d371de`；运行前后已有 IDE/DS_Store 改动保持原样。
- macOS Apple Silicon，CPython 3.14.7；Docker PostgreSQL 18.6，已实际迁移到 `0002_platform`。
- DeepSeek：`https://api.deepseek.com`，`deepseek-flash`，上下文 1,048,576，桥接显式关闭 thinking，单次输出最多 4096 tokens。模型列表已用用户凭据请求成功；参数参考 [DeepSeek 官方文档](https://api-docs.deepseek.com/quick_start/pricing/)。远程模型别名不保证未来权重不变。
- Deta 每次最多 12 次模型尝试、24 次工具调度、240 秒；Eyes 超时 300 秒、评分超时 40 秒。
- 控制端用 Eyes 锁定环境；Agent/评分器用 `data/deta-integration/venv` 联合安装两项目，实际依赖已冻结到 `data/deta-integration/dependencies.txt`，不是对两个锁文件完全相同的声明。

两个项目的 `.env` 均已配置同一个模型密钥，权限为 0600。Deta 原 `.env` 的备份位于 `.deta/config-backup-before-eyes.env`。Eyes 的目标快照只保存 `env:OPENAI_API_KEY` 引用。Eyes 平台管理/Runner 令牌与 DeepSeek 模型密钥各自独立；这次使用确定性代码评分，Eyes 控制 API 不调用模型。

## 文件与本地服务

- `bridge.py`：准备起始文件、调用 Deta、转发非增量生命周期事件、快照轨迹和 spans；正文里的当前密钥会被遮盖。
- `scorer.py`：独立进程执行冻结代码并返回可追溯 pass/fail。
- `coding-smoke.jsonl`：本次请求下建立的 3 个基础编码评测任务，不是仓库单元测试，也不是真实业务基准集。
- `publish.py`：通过公开 API 发布目标/数据集/评分器及创建实验；每次执行创建新版本和新实验。
- `run_runner.py`：从本地凭据文件启动 Runner，不在终端输出令牌。

本机配置和原始证据放在 Git 忽略的 `data/deta-integration/`：`runner.toml`、`manage.json`、`runner-credential.json`、`results.json`、`case-runs.json`、`metrics.json`、`evidence/<case_id>/`、`console.png`。模型密钥不在这些公开版本对象中。

当前服务使用独立端口，保留原先 8000/5173 服务：

| 服务 | 地址 |
| --- | --- |
| 控制台 | http://127.0.0.1:5174 |
| API | http://127.0.0.1:8001 |
| PostgreSQL | 127.0.0.1:5433，容器 eyes-deta-postgres-1 |

浏览器已连接本地项目并打开实验。刷新后需重新连接；在 Eyes 根目录运行下列命令可把本地项目令牌复制到剪贴板，再粘贴到“连接设置”。不要把模型密钥当作项目令牌。

```sh
uv run python -c 'import json, subprocess; from pathlib import Path; subprocess.run(["pbcopy"], input=json.loads(Path("data/deta-integration/manage.json").read_text())["token"], text=True, check=True)'
```

本机服务重启命令（分别在终端运行，工作目录为 Eyes 根目录）：

```sh
docker compose -p eyes-deta --env-file data/deta-integration/compose.env -f deploy/compose.yaml up -d postgres
uv run uvicorn eyes.server.api.app:create_app --factory --host 127.0.0.1 --port 8001
uv run eyes-scheduler
uv run --env-file .env python integrations/deta/run_runner.py
EYES_API_PROXY_TARGET=http://127.0.0.1:8001 npm --prefix frontend run dev -- --port 5174
```

对相同配置再次执行，直接在实验详情点“关联重跑”，现有 Runner 令牌允许本轮目标。若修改数据集、桥接或评分器，先更新 plugins 摘要并运行 `publish.py`；由于新目标具有新版本 ID，需为新目标签发对应范围的 Runner 令牌，再重启 Runner，不能沿用旧目标权限冒充已接入。

```sh
uv run eyes-runner --config data/deta-integration/runner.toml plugins > data/deta-integration/plugins.json
uv run --env-file .env python integrations/deta/publish.py
```

## 验证边界

已执行 Ruff lint、格式检查、`git diff --check`、真实数据库迁移、API readiness、3 次真实 Deta 执行、3 次独立评分、产物下载和浏览器结果核对。

这是基础功能冒烟评测，不代表复杂仓库修复、多文件任务、长上下文/压缩、恢复、取消、并发、安全隔离或稳定性验收。Deta bash 创建独立子进程组，因此绑定声明 `execution_scope=external`、不声明取消保证，也不将目录隔离宣称为操作系统沙箱；环境隔离能力为 false，串行执行。可信本机代码仍有宿主机权限。接入报告不改变平台其他尚未完成的验收结论。
