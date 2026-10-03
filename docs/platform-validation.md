# 平台功能验证记录

日期：2026-10-03。应用包 0.1.0；新迁移 `0002_platform`。本轮范围为回归/CI、执行与证据机制、部署运维。真实 HTTP/Python Agent 接入继续放在最后。

## 实现范围

- ComparisonReport、显式评分配对和 ScoreRun 选择、可比性原因、用例等权汇总、固定质量门槛及幂等发布。
- 开发者 CLI：导入、创建、查询、等待、结果、取消、比较、报告、门槛、评分 retry/rescore。
- 实验冻结 evidence_wait_seconds；独立 EvidenceWait、截止前清单选择、初始评分与重新评分分离。
- 等待/排队/活动评分取消；原清单评分重试；Runner 迟到上传封存与确认后回收。
- 证据过期占位、文件回收、审计、维护锁、备份及空目标恢复；可选周期维护进程和可配置部署端口。

本轮没有新增或修改测试文件、用例、fixtures、mocks、模拟 Agent 或内联断言。验证使用当前工具命令、真实 PostgreSQL 和原有 UI Review 项目的独立副本；没有创建执行输出、事件、产物或评分来替代真实 Agent 数据。

## 环境及隔离

- 宿主机 macOS Apple Silicon，项目 CPython 3.14.7。
- 原 `eyes-ui-review-20261003` PostgreSQL 容器保持停止。从其停止状态的数据卷只读复制到新卷 `eyes-platform-review-20261003`。
- 独立 PostgreSQL 17 数据副本映射 `127.0.0.1:55433`，只包含原项目已发布的配置、两条用例和两次排队实验；API 验证端口为 8043。
- 另建全新 Compose 项目 `eyes-platform-release`，使用 PostgreSQL 18.6、Python 3.14.7 容器及原前端构建配置。独立端口为 PostgreSQL 55434、API 18043、Web 18080。
- 临时配置、命令输出、报告、备份位于 `/private/tmp/eyes-platform-20261003`；其中配置和令牌不提交到项目。
- 项目当前未初始化 Git，本轮没有 commit、push 或 PR。

## 已运行结果

| 检查 | 实际结果 |
| --- | --- |
| `uv sync --frozen` | 成功安装新增 eyes/eyes-ops 入口，无新增依赖 |
| Ruff、格式、compileall、uv build | 61 个 Python 文件检查通过，sdist/wheel 生成成功 |
| `alembic upgrade head` | PostgreSQL 17 上实际从 0001 升到 0002 |
| `alembic check` | No new upgrade operations detected |
| 迁移回滚再升级 | 独立恢复数据库 0002→0001→0002 成功，模型一致性再次通过 |
| `/health/ready` | 独立 API 返回 200、0002_platform；包含证据卷可写检查 |
| 未认证 `/v1/experiments` | 返回 401 |
| 已认证 CLI 查询 | 读取原项目两次实验成功 |
| 创建回归报告 | 实际持久化 2 行用例比较，识别 timeout_seconds 差异，门槛 inconclusive |
| `eyes gate` | 初始报告退出码 2，包含 no_valid_scores、comparable_coverage、experiment_not_finished |
| 相同报告请求重放 | 返回相同报告 ID、摘要与规范化 JSON 内容 |
| 排队取消 | 取消独立副本中的候选实验，旧报告内容保持不变 |
| 取消后的新报告 | execution_success_rate 未达门槛，状态 fail，CLI 退出码 1 |
| CLI 无效命令参数 | 配置错误退出码 3，与 inconclusive 区分 |
| Scheduler 单次扫描 | 正常完成；无已领取任务，四项原有计数均为 0 |
| `eyes-ops audit` | 数据引用审计通过；ready 产物、清单和评分数均为 0 |
| `eyes-ops maintain` / `--apply` | 预览与执行均成功，无符合条件的证据或文件 |
| `eyes-ops backup` | 使用 PostgreSQL 容器内 pg_dump 和导出快照，创建完成清单成功 |
| `eyes-ops restore` | 恢复到新空数据库成功，含回归报告的第二次备份也恢复成功，随后 audit 通过 |
| 恢复到非空数据库 | 明确拒绝，退出码 3；现有数据未覆盖 |
| 控制端镜像构建 | Docker 实际构建成功，使用锁定依赖与非 root 用户 |
| 完整 Compose 启动 | PostgreSQL/API healthy；migrate 退出码 0；Scheduler、Web 运行 |
| Web 与反向代理 | Web 首页 HTTP 200，`/api/health/ready` HTTP 200 且版本为 0002 |
| Compose 命名卷停写备份/恢复 | 按文档停止写入，pg_dump + compose cp，恢复到独立新项目后 audit 通过，API/代理均返回 200；源部署无业务产物 |
| 最终 OpenAPI / operations | 34 个路径；新增 ComparisonCreate/EvidenceClose schema；运行状态包含证据等待、评分错误、最老排队时间与丢弃计数 |

报告示例标识：初始 `9fa9b0ed-e005-4491-a812-8c1dadc57fcd`；取消后的新报告 `40fcaa11-f826-4a7c-a8ef-9e59dfbca192`。这些记录只属于独立验证副本，不代表实际 Agent 评分。

## 发现并修复的运行问题

1. 首次迁移的 SQL JSON 字面量 `:true` 被 SQLAlchemy 当作参数解析。迁移事务回滚；改用 jsonb_build_object 后实际升级成功。
2. 首次报告发布时汇总的 experiment_id 是 UUID 对象，不能直接序列化到报告 JSON。统一输出为字符串后发布成功。
3. 初次字节级比较报告不同，原因是 PostgreSQL JSONB 返回键顺序改变；规范化 JSON 后内容完全一致。
4. Docker Buildx 默认写 `~/.docker/buildx/activity` 被工作区权限拒绝。把 Buildx 缓存配置放到可写 `/private/tmp/eyes-platform-buildx` 后构建成功，未更改系统权限。

## 证据边界

已验证的业务链到“实际配置/实验记录 → 回归快照 → 取消 → 新报告 → CLI 门槛”，以及数据库迁移和无产物数据集的备份恢复。静态检查、数据库与部署检查没有替代以下验收：

- 有真实评分的改善、退化、数值方向、重复运行等权计算和 gate pass。
- 真实 Agent 产生的缺证据等待、截止前/截止后上传、封存确认、产物过期及载荷清除。
- 多 Runner 并发配额、网络中断、租约失效、活动评分取消、进程崩溃和未知外部操作核对。
- 含 ready 产物和真实事件/评分的备份恢复、清理失败后再次回收。
- 容量、吞吐和长期运行实测。

未修改前端页面。本轮 Web 验证仅针对部署静态资源与 API 代理，不新增视觉验收结论。真实 Agent 接入、上述执行链路与运行风险在后续联调阶段验证。


## 收尾

验证结束后关闭本轮独立 API，并停止/移除两个临时 Compose 项目的容器，保留其数据卷和备份供检查；独立 PostgreSQL 17 副本容器停止。未升级或改写原 UI Review 数据卷，也未更改原 API 的配置。实际使用需先备份并升级数据库到 0002_platform，再重启控制端、Scheduler 与 Runner。

## 审查后修复（2026-10-03）

- Runner 封存前确认本地证据文件和 outbox 待上传/被拒绝记录均为空，再清除当前转移失败计数；完成上报时的旧计数以 `local_transfer_failures_at_completion` 保留。不可恢复的采集缺口仍阻止 sealed，原完成请求不改写。
- CLI 的 create/compare 使用 `exclude_unset=True` 序列化已校验请求，保留字段省略信息，使旧实验请求可进入服务端的幂等兼容分支。
- 对两个修改的 Python 文件运行 Ruff lint、格式检查和 compileall，均通过；`eyes --help` 入口检查通过。已核对代码差异及平台说明。
- 本次修复未运行真实 outbox 积压恢复或旧实验 HTTP 重放；不将静态检查记为行为复现。未新增或修改测试，未更改数据库、迁移和运行中的服务。
