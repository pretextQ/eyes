# 第一阶段维护复验（2026-11-11）

Windows PowerShell、本机 Docker Desktop Linux Engine 29.8.2、PostgreSQL 18.6，运行源码基线 `897e2d1`。使用只读挂载源码和迁移的 `eyes-control:local`，另建数据库及证据卷。原始日志、命令输出和备份副本保留在 Git 忽略的 `data/maintenance-20261111/`。

## 0008 迁移与旧备份恢复

| 检查 | 实际结果 |
| --- | --- |
| 0007 备份 | 使用 [10 月 14 日备份往返](../cancellation-audit-20261014.md#真实结果)留下的 0007 dump 和 27 份原证据，在新库中恢复并以 `b0701c0` 的 `eyes-ops backup` 重新打包。用当前 `eyes-ops restore` 恢复到另一个空库和证据目录，返回 audit=ok，27 份 ready 产物、49 份清单、16 条评分。旧 Runner 凭据均已撤销，原管理及读取凭据保持启用。 |
| 0008 真实升降级 | 在上述恢复库运行 `alembic upgrade head`、`alembic downgrade -1`、再次 `alembic upgrade head`、`alembic check`。确认两个索引按迁移增删，最终模型无差异。逐表比较按 ID 排序的整行 JSON 摘要，恢复及升降级前后 47 个工作项、17 个 Attempt、352 个事件、49 份证据清单、27 条产物元数据、16 条评分、1 份报告和 11 条取消审计一致。该副本没有观测行。 |
| 查询计划 | 对恢复库中实际实验和 Attempt 分别执行 `EXPLAIN (ANALYZE, BUFFERS)`。0007 与 0008 的默认计划均选择顺序扫描，返回 6 和 2 行。样本共 47 个工作项，未测得能归因于索引的性能改善。 |
| 恢复后的服务 | UID 10001 执行 `eyes-ops audit` 通过，`/health/ready` 返回 `0008_work_indexes`。用项目读取凭据通过 API 下载 1 份真实产物，146 字节及 SHA-256 与恢复元数据一致。 |
| 0005 备份 | 从 [10 月 11 日备份](../backup-release-review-20261011.md#当前工具的实际备份恢复)恢复到另一空库，`alembic upgrade head` 经 0006、0007 到 0008。升级前后两项原 unknown 工作 ID 和占额状态一致，审计均为 ok，含 47 份 ready 产物、86 份清单、25 条评分。 |

首轮 0007 打包只挂载旧源码，镜像内新迁移导致工具要求 0008。改为同时挂载 `b0701c0` 的迁移后通过。0005 原备份只读挂载对服务用户不可读，保留原目录权限，在独立卷内复制并仅将副本交给 UID 10001 后复验通过。0006 作为源版本的备份恢复仍引用 [10 月 14 日历史验证](../cancellation-audit-20261014.md#真实结果)，本轮实际走过 0006 的升级步骤。

## 取消、领取和评分诊断

在 `2e27d6f` 源码上使用 [MewCode 回归](../mewcode-regression-20261111.md)的候选实验和真实 Attempt。通过公开 API 新建两次重评分，分别检查取消后未确认停止和普通租约到期。使用限定到候选目标及 score 的临时 Runner 凭据直接领取真实工作；Agent 和业务 Runner 已停止，本轮没有新的模型调用或伪造评分结果。

1. 领取第一项重评分后，从管理 API 请求取消。取消审计 `5e158a12-67bf-4b7d-8383-f0fd06d6646f` 持久化，实验为 `cancel_requested`。
2. 取消后另发起第二项重评分并领取。分别在取消、重评分入队和领取完成后读取实验，三次均为 `cancel_requested`。
3. 第一项在 35 秒后续租，心跳返回 `cancel_requested=true`。保留租约跨过 60 秒取消宽限期且不提交停止确认。第二项不续租。实际 Scheduler 周期扫描后，两项评分均为 `error`：第一项为 `scoring cancelled; stop was not confirmed before the grace deadline`，第二项为 `score lease lost or submission window ended`。
4. PostgreSQL 确认两项工作均为 `completed`、占额已释放、令牌已清空，实验最终 `completed`，先前固定回归报告完整响应一致。临时 Runner 凭据已撤销。

验证覆盖了取消后重评分入队再领取的实际事务顺序，以及两条未收到评分回执的路径。活动外部 Agent 停止确认和不同进程争用的完整时序仍待专项验收。`ruff check`、`ruff format --check` 通过。
