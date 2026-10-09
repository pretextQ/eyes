# 2026-10-09：Windows / MewCode 真实评测

本次完成单 Agent 功能闭环，不覆盖版本回归、故障恢复或容量验收。接入方式、凭据边界与重启步骤见 [MewCode 接入](../integrations/mewcode/README.md)。历史 Deta/Zeta 的 macOS 验证仍是历史记录，不能作为本机 Windows 能力证明。

## 实际结果

最终实验：`087a0f7c-bfd5-44d0-b27c-d812fc45cbd9`。

| 用例 | 执行 | 独立评分 | 证据 | Agent span 耗时 |
| --- | --- | --- | --- | --- |
| fix-mean | succeeded | completed / pass，4/4 | sealed；清理成功 | 4.39 秒 |
| integer-cli | succeeded | completed / pass，4/4 | sealed；清理成功 | 3.04 秒 |
| stable-unique | succeeded | completed / pass，4/4 | sealed；清理成功 | 4.65 秒 |

计划 3、执行成功 3、有效评分 3、通过 3、未知 0、失败尝试 0、未解决评分 0。每用例一次，串行。耗时来自真实 `mewcode.run` SDK span，不含排队、准备、传输和评分，不作为性能或稳定性承诺。

53 条事件，包含 8 次 ToolUseEvent、8 次 ToolResultEvent、11 次 UsageEvent。provider 返回 usage 累计 input_tokens=2681、output_tokens=1602；它是提供方返回值，不推断其完整计费口径。6 份产物（3 份代码、3 份轨迹）已从 Eyes API 下载，按冻结评分输入的元数据核对大小和 SHA-256。三次采集的 dropped、capture、artifact_capture、truncated、pending、rejected、local_transfer_failures 均为 0。Runner 结束状态 pending/rejected/quarantined=0，retained_work=6（两轮及重评分留下的六份评分 trace/payload，不是六个活跃任务）。

Web 已核对实验列表、3/3 执行、3/3 有效评分及通过、逐用例 sealed/清理、真实工具事件、评分理由和固定清单引用。没有修改页面或添加演示数据。截图见本机证据目录。

## 版本和环境

- Eyes 提交：`732886602a8813df696de69464acbdc9da5efd3a`，本轮新增 `integrations/mewcode/` 和文档；核心源码未改。
- MewCode 提交：`3f104082b6c5ca53efe273630bf08f67f1fc3ff5`；运行前后 Git 工作区干净，源码摘要 `a007cfa9bcfb9d2f1051a154c6f64d2b42542fc83061d45ba046787d0b94e35d`。摘要基于各 Python 文件 SHA-256 的排序映射，不是整个仓库内容摘要。
- 目标版本：`dd6efa40-4dab-4391-916f-893beb523e75`；数据集：`dea02eb8-c96f-4d75-9a55-fdb01ce17f39`；评分器：`d9f88a2e-c3e6-49b7-bcdd-aa74af98cb31`。
- 原评分器文件摘要：`11badc0d2397a20b51d7c41fcdbb246b68ca2dca600646b2a6f95ccd234a89b6`；评测 JSONL 和评分器均原样复用。
- PostgreSQL 15.17 实际迁移至 `0004_experiment_batches`；Windows 控制/调度环境 CPython 3.14.4，Linux API/Runner/Agent/scorer CPython 3.14.7。Docker Engine 29.4.2，Node 22.14.0。
- Linux 运行镜像：`sha256:420dba75f4b41b95976e91e0d590cfc9d1fb3397a8a64b39c1c21ed167ceca2a`。实际依赖及桥接文件摘要保存于本机证据，不能仅用 Git 提交代表组合环境。

## 保留的失败和调整

第一次实验 `50a77adb-a9a6-42b2-9eb6-bbbf956c7905` 的三次真实 Agent 执行成功，但原生 Windows API 的 `LocalArtifactStore.publish` 对目录 `os.open/fsync` 返回 PermissionError，产物 PUT=500。初始三个评分均 insufficient_evidence，不能报告通过。

把 API 切换到 Linux 镜像，继续连接原数据库和原证据目录。Runner 重传已有事件/产物，三次最新清单成为 sealed。通过公开 rescore API 创建新的 ScoreRun，同一批冻结代码评分 3/3 pass。旧评分没有覆盖；第一轮汇总按最早评分仍是 0/3 有效，符合当前设计。随后创建关联实验验证修正部署，才得到本页报告的原始汇总 3/3 pass。总共六次真实 Agent 执行，没有模拟或用手写代码替代 Agent。

Docker Desktop 首先因 `dockerInference` 无法访问而退出，备份整个临时 run 目录后又发现 secrets-engine 套接字同类错误。通过官方 `docker desktop stop --force`、备份两个运行时目录、重新 start 恢复。保留 `C:\Users\32519\AppData\Local\Docker\run.eyes-20261009-backup*` 与 `C:\Users\32519\AppData\Local\docker-secrets-engine.eyes-20261009-backup`，没有恢复出厂设置或删除镜像/数据卷。此类故障也见 [Docker Desktop 维护仓库的问题记录](https://github.com/docker/desktop-feedback/issues/460)，这里只据本机日志确认实际故障和修复结果。

`uv sync --frozen` 因清华镜像 wheel 下载 403 失败；用官方 PyPI 解析满足项目约束的环境，保留实际依赖。Docker 拉取 Python 3.14.7-slim、3.14-slim-bookworm、PostgreSQL 18.6 因 tiny layer 短读 EOF 失败；改用缓存基础镜像安装实际 Python 3.14.7及本机独立 PostgreSQL。完整 Compose 部署未验收。原生 Scheduler 启动脚本首次带多余 argv 失败，修正后正常持续扫描。

## 验证与证据位置

实际执行：PostgreSQL initdb/启动/迁移；API 和前端代理 readiness；Linux Python/插件读取；模型列表真实请求；六次真实 Agent 执行；首轮三次补充评分及最终三次评分；产物下载完整性核对；Web 显示核对。Ruff lint/format、bridge 导入、Compose config、前端 `npm ci` 和 `npm run build`、`git diff --check` 通过。未新增/修改/运行仓库测试。npm 安装报告 7 项 high 级依赖审计问题，本轮未自动升级依赖或宣称生产发布验收。

本机 Git 忽略目录 `D:\projects\eyes\data\mewcode-integration\`：

- `versions.json`、`integration-files.json`、`runtime-bridge.json`、`image-id.json`、两份 dependencies：版本/实际环境。
- `published.json`、`experiment*.json`、`results.json`、`case-runs.json`、`acceptance.json`：固定配置与最终事实。
- `evidence/<case_id>/<attempt_id>/`：原始事件、清单、代码、轨迹、冻结评分输入；同时保留两轮尝试，各有独立 UUID。
- `artifact-verification.json`：最终六份下载的摘要/大小；第一轮索引在 `first-experiment/`。
- `first-experiment/`、`*-before-rescore.json`、`rescore-requests.json`：原始失败与新评分历史。
- `runner/`：实际 journal/评分 trace，`runner-status.json`、`runner.log`、API/scheduler/postgres 日志：状态与故障事实。
- `console.png`、`scores.png`、`events.png`、`case-score.png`：Web 核对截图。
- `build-runtime*.log`、`pull-python.log`、`initdb.log`：实际构建/环境失败记录。

凭据文件和数据库目录为私有本机数据，不提交、不分享。原评分口径只有十二项函数/CLI 检查；本轮结论不能推广到完整指令遵循、复杂仓库修复、对抗性隔离、远端取消/幂等/查询、重启恢复、版本回归及容量。取消和恢复能力按接入声明为 false，独立目录及本地进程停止不能用于证明安全沙箱或远端已停止。
