# MewCode 版本回归复验

2026-11-11（Asia/Shanghai）。Eyes 源码 `bcd8cfe`，Windows PowerShell、本机 Docker Desktop 4.94.0 / Linux Engine 29.8.2、Python 3.14.7、PostgreSQL 18.6 / `0008_work_indexes`。本轮使用新数据库、证据卷、项目、Runner 状态与两个独立 Agent 状态卷。原始请求、响应、运行日志、依赖清单和下载字节保留在本地 Git 忽略的 `data/regression-20261111/`。

## 冻结材料

基线采用上轮已运行的 MewCode `3f104082b6c5ca53efe273630bf08f67f1fc3ff5`，候选采用本轮核对的远端主线 `46ea7393381d27079b877d13f9ed33c88821dc03`。用 `git archive` 导出后分别只读挂载到 `/opt/mewcode`。启动前在两个容器配置下实际导入 bridge，核对 MewCode 加载路径及 Python 文件字节映射，发现响应也返回相应版本。摘要使用包内相对路径为键、文件 SHA-256 为值，按键排序序列化后再取 SHA-256。

| 角色 | 加载源码摘要 | 实验 |
| --- | --- | --- |
| 基线 | `2c6e33861012acf53329a736582dbd3746c59bf94be771a725c884081b4d6c37` | `a77d87a4-6612-4b2a-94d0-ac2f088f6a03` |
| 候选 | `8e4f95f53252e497410426f6416a268397b8c05a311c357285c36fb9510b6eb1` | `83f45261-c208-48a7-94fd-6fe34cb9f8f1` |

- 同一发布数据集 `1f14886e-0dfa-4e62-a674-c6c920f99bd3` 复用 [原三项任务](../integrations/deta/coding-smoke.jsonl)，文件 SHA-256 为 `9e868ae0c53f1e2f88d6114b5c76e591647ecd78ef6b6d3882cbaf8b49771e4b`。
- 同一发布评分器 `069ff5d5-4c1d-4ea2-8782-9df8f95e17b9` 复用 [deta_code](../integrations/deta/scorer.py)。Runner `plugins` 返回实现摘要 `3e72cfd6a721cddd420f9d850cf79366545e886ec59b7377424c01fb0737d826`，要求 output、events、artifacts、sealed，评分超时 40 秒。
- 两侧共用同一 Agent 镜像及无密钥参数文件。DeepSeek OpenAI 兼容接口，`deepseek-flash`、thinking=false、128000 上下文、8192 输出上限、最多 12 轮、`dontAsk`。模型别名没有固定远端权重。实验均为并发 1、重复 1、执行超时 300 秒、证据等待 15 秒、`first_success`。采集包括任务边界、HTTP Agent 轨迹和产物。

两次标准构建均在 PyPI 下载构建依赖时超时。实际使用已有 `eyes-control:local` 的冻结依赖，只读挂载当前 Eyes 源码和迁移，API 加载的 Python 源码映射与工作区一致，readiness 返回 0008。Agent 镜像基于同一控制镜像，补入从候选锁导出的缺失依赖，`uv pip check` 通过。两侧共享这一组合环境，包含 `pydantic 2.13.5`、`openai 3.36.1`、`mcp 1.30.0`、`aiohttp 3.14.5`。首次 Compose 启动选中了宿主机已占用的 5432，改用独立端口 55491 后通过。本轮干净镜像构建仍受下载超时阻塞。

## 重复执行与复查

1. 按 [MewCode 独立环境说明](../integrations/mewcode/README.md#从干净环境构建接入镜像)启动控制平台，确认 readiness。为两个提交分别导出源码并启动隔离的 HTTP Agent。记录实际加载源码、依赖、模型参数和能力。可用同一镜像和不同只读源码挂载来固定依赖；本轮两个 Agent 和 Runner 共享 API 容器的网络命名空间，Agent 只在容器内的不同 loopback 端口监听。
2. 按 [HTTP 能力发现与发布](agent-http-runtime.md#发布并执行统一协议目标)发布两个目标版本。导入一次真实任务集，按 `eyes-runner plugins` 的摘要发布一次评分器。创建两个实验请求，固定数据集、评分器和运行参数，仅替换 `target_version_id`。启动带对应目标和工作类型权限的 Runner。
3. 在 PowerShell 中设置实际 `EYES_URL` 和 `EYES_TOKEN` 后执行下面的命令。`baseline.json` 和 `candidate.json` 使用 [ExperimentCreate](../src/eyes/contracts/work.py) 字段。`comparison.json` 使用两个实际实验 UUID 和同一评分器 UUID，格式见 [固定报告请求](platform.md#创建报告)。传输重试复用原请求键，新一轮执行或报告使用新键。

   ```powershell
   uv run eyes create --file baseline.json --key release-42-baseline
   uv run eyes create --file candidate.json --key release-42-candidate
   uv run eyes wait BASELINE_UUID --deadline 600
   uv run eyes wait CANDIDATE_UUID --deadline 600
   uv run eyes results BASELINE_UUID
   uv run eyes results CANDIDATE_UUID
   uv run eyes compare --file comparison.json --key release-42-comparison
   uv run eyes report REPORT_UUID
   uv run eyes gate REPORT_UUID
   $LASTEXITCODE
   ```

4. 查看报告中每条用例的 `reasons`、两侧的执行与评分状态，以及分类和分母。由 `case_run_id` 读实验用例详情，由 `attempt_id` 读取该尝试和 `/scores`、`/manifests`，按 `score_run_id`、`manifest_id`、`manifest_digest` 定位固定证据。检查评分引用均属于清单，通过 [产物内容接口](backend.md#api-清单)下载引用的字节。执行失败、取消、环境差异和证据不足保留各自原因。

## 本轮结果

`fix-mean`、`integer-cli`、`stable-unique` 在两侧均执行成功并评分 `completed/pass`。两侧执行成功率、评分覆盖率、有效评分通过率均为 3/3，取消、失败和未知执行均为 0。可比覆盖 3/3，三项均 `unchanged`。报告保留目标配置变化（服务地址及版本发现）和原任务外部环境限制。真实改善与退化仍待观测，本轮每个用例只运行一次。

- 固定报告 `513b67e1-b846-4bd4-a661-d07bf7451bd3`，摘要 `49452d6969d8a8bb2de742c7a8e3f92191a0376056e0dbfe7c045f3167907e10`。CLI `report` 回读一致，`gate` 返回 `pass`、退出码 0。本轮其它退出码沿用 [10 月 11 日的历史验证](deployment-regression-20261011.md#历史选择证据和-cli)。
- 逐项从报告绑定到 6 个 Attempt、6 个 ScoreRun 和对应清单，清单包含 130 条事件引用。16 份清单产物经授权 API 下载，大小与 SHA-256 全部匹配隔离库的登记元数据。采集时首次从用例详情读取产物元数据遇到缺字段，改从隔离库只读查询后完成核对。
- 对候选 `fix-mean` 用同一评分器追加评分 `080b61c7-d5f7-43a0-95b0-6fe2af24f39d`，结果 `completed/pass`。旧报告回读字节一致，新默认报告 `35bf0963-564e-4614-bf65-c40e38e4aba6` 仍选择原评分 `63a57e63-337f-449a-82cd-642d7ca5c76c`。
