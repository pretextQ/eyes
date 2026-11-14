# Eyes 项目审查（复核版）

- 检查对象：`D:\projects\eyes`，HEAD `c94d500`（2026-10-24），工作树仅 `.agent-teams/` 未跟踪
- 检查时间：2026-11-03（Asia/Shanghai）
- 执行方式：主线程只读源码审查 + 实际运行静态检查 + 若干一次性 Python 探针（异常捕获语义、JSONL 解析、模型索引反射）
- 约束：全程只读，未修改源码、配置或数据；未启动 PostgreSQL / Docker / API / Runner（Docker daemon 未运行）；未新增测试
- 文档性质：本文件是**待修复清单**，不是验收记录；结论分"已确认"与"已撤销"两类，撤销项用于避免后续重复修复

## 一、结论摘要

| 级别 | 数量 | 说明 |
| --- | --- | --- |
| 已确认 | 1 中 + 4 低 | 均有明确源码位置与触发路径，可直接修复 |
| 已撤销 | 6 | 经复核属文档化设计或原判断有误，**不要按原结论修改** |
| 未验证风险 | 3 | 需 PostgreSQL/真实材料才能确认，不列为缺陷；其中 2 项同时是修复后的验证方法 |

本轮未发现阻断级或安全级缺陷。仓库零测试资产、CI 无 test job 的现状延续，属既定策略（`AGENT.md` 禁止未经授权新增测试），不重复列为缺陷。

## 二、已确认问题（建议修复）

### P1：`work_items` 缺少按 `experiment_id` / `attempt_id` 的索引

**位置**

- [models.py](../../src/eyes/server/storage/models.py) 第 282-283 行：`WorkItem` 只声明 `ix_work_queue` 与 `ix_work_reservations`
- 迁移 [0001_control_plane.py](../../migrations/versions/0001_control_plane.py) 第 419-430 行与模型一致；后续迁移未补索引
- 运行时反射结果确认（2026-11-03 实际执行）：
  ```
  WorkItem indexes: [('ix_work_queue', ['project_id','kind','status','created_at','id']),
                     ('ix_work_reservations', ['kind','reserved','target_scope_id','experiment_id'])]
  ```

**受影响的热路径**（PostgreSQL 不会为外键自动建索引）

| 调用点 | 过滤条件 | 现有索引为何用不上 |
| --- | --- | --- |
| [service.py:408-425](../../src/eyes/server/scheduling/service.py#L408-L425) `refresh_experiment`，每次工作完成/取消都执行 | `experiment_id` 单列 | `ix_work_reservations` 前导列是 `kind`，`experiment_id` 在第 4 位 |
| [batches.py:129-145](../../src/eyes/server/experiments/batches.py#L129-L145) `detail` | `experiment_id IN (...) + kind` | 同上，且需分组 |
| [service.py:511-515](../../src/eyes/server/scheduling/service.py#L511-L515) `_cancel` | `experiment_id + kind` | 只能用到 `kind` 前导列 |
| [evidence/service.py:519-525](../../src/eyes/server/evidence/service.py#L519-L525) `download_path` | `runner_id + attempt_id` | 无任何索引覆盖 |
| [recovery.py:58-60](../../src/eyes/server/scheduling/recovery.py#L58-L60) `claim` | `status/completed` + JSONB `Attempt.result["source"]` | 无索引，且 JSONB 路径等值过滤 |

同时 `refresh_experiment` 会一次性加载该实验全部 `WorkItem.status`（上限由 `max_experiment_runs=100000` 决定），叠加缺失索引后是"每次完成都顺序扫描 + 大列表"。

**影响**：随 `work_items` 增长而线性放大的调度延迟；不属于正确性缺陷。

**建议修复**

1. 新增迁移 `0008_work_indexes`（或下一个可用号），建立：
   - `ix_work_items_experiment` on `(experiment_id)`
   - `ix_work_items_attempt` on `(attempt_id)`
   - 视实际查询再评估 `(runner_id, attempt_id)`
2. 同步在 [models.py](../../src/eyes/server/storage/models.py) 的 `WorkItem.__table_args__` 声明，否则 CI 的 `alembic check` 会报模型与迁移不一致（见 [.github/workflows/ci.yml](../../.github/workflows/ci.yml) 的 migrations job）。
3. 可顺带把 `refresh_experiment` 改为聚合查询（如按状态 `group by`），减少每次完成的全量行读取。

**验证方式**：`alembic upgrade head` / `alembic downgrade -1` / `alembic check`；在真实 PostgreSQL 上对上述查询做 `EXPLAIN (ANALYZE)` 对比。

### P2：`sweep` 对被取消的评分复用"租约丢失"文案

**位置**：[service.py:621-633](../../src/eyes/server/scheduling/service.py#L621-L633)

```python
cancelled = (score.cancel_requested_at and ... <= current_time)
if expired or submission_deadline <= current_time or cancelled:
    score.status = "error"
    score.result = ScoreOutput(..., reason="score lease lost or submission window ended")
```

**说明**：`error` 本身是文档规定的行为（见 [platform.md](../platform.md) 第 157 行"未按时结束或失去租约保留 error 诊断"、[backend.md](../backend.md) 第 191 行），**不要改成 skipped**。问题只在原因文案：Cancellation 分支与租约丢失共用了同一句 `reason`，排障时无法区分是"取消后 Runner 未上报"还是"租约到期"。

**建议修复**：为 `cancelled` 分支单独设置 reason（例如 `"scoring cancelled; stop not confirmed before grace deadline"`），并保持 `status="error"` 与 `counts["score_errors"]` 语义不变。

### P2：`claim()` 置 `running` 时绕过 `cancel_requested` 守卫

**位置**

- [service.py:297](../../src/eyes/server/scheduling/service.py#L297)：`experiment.status = "running"` 无条件执行（execute 与 score 领取共用）
- [service.py:421-423](../../src/eyes/server/scheduling/service.py#L421-L423)：`refresh_experiment` 对 `cancel_requested` 有 `if experiment.status != "cancel_requested"` 保护

**触发路径**（狭窄但真实）：实验处于 `cancel_requested` 且仍有 `claimed` 工作；此时对**已 succeeded** 的 Attempt 执行 `POST /v1/attempts/{id}/rescore`（[routes.py:461-468](../../src/eyes/server/api/routes.py#L461-L468)，`evaluation.rescore` 只校验 `attempt.status == "succeeded"`，不校验实验状态）→ `enqueue` 新建 queued score 工作 → Runner 领取 → `claim()` 把实验状态改回 `running`，覆盖 `cancel_requested`。

**注意**：`_cancel` 会把所有 `queued` 工作置为 `cancelled`（[service.py:516-518](../../src/eyes/server/scheduling/service.py#L516-L518)、`:535-540`），所以取消完成后**没有** queued 工作可供领取；上述路径是唯一触发方式，不能描述为"普遍覆盖"。

**影响**：取消事实本身仍保存在 `cancellation_audits`、Attempt/CaseRun 状态与 `cancelled_runs` 中；丢失的是实验级"等待停止确认"的可见状态。

**建议修复**：`claim()` 内改为与 `refresh_experiment` 一致的守卫，例如仅在 `experiment.status != "cancel_requested"` 时写 `running`。

### P3：观测详情页每次事件数变化都重拉全部已加载分页

**位置**：[Observation.tsx:463-491](../../frontend/src/pages/Observation.tsx#L463-L491)，`limit` 递增在 `:658`

查询键包含 `metadata.data?.metrics.events`（`metadata` 每 2 秒轮询），因此**不是"每 2 秒重拉"**，而是每来一个新事件就触发一次详情查询；该查询从 `offset=0` 起循环取页直到 `limit`，用户点"加载更多"后 `limit` 每次 +200。于是每批新事件都会重新下载全部已加载页，长链路总体接近 O(n²)。

**建议修复**：改为增量追加（只请求上次 `offset` 之后的新页），或按页缓存并以最后已知 `metrics.events` 为水位。

**验证方式**：Windows 浏览器 DevTools Network 面板观察长运行时的请求次数与重复字节。

### P3：观测详情读取接口对只读请求加行锁

**位置**：[observation/routes.py:127-151](../../src/eyes/server/observation/routes.py#L127-L151)，第 131 行 `scoped(..., lock=True)`

`GET /v1/observation/runs/{run_id}` 使用 `SELECT ... FOR UPDATE`，锁持有到请求事务结束；而 [observation/service.py:91-105](../../src/eyes/server/observation/service.py#L91-L105) 的写入路径同样对同一 run 行加锁。前端按 2 秒轮询该接口，会与采集端串行化。

**说明**：保留 `FOR UPDATE` 可能是为了让"过期"与"读取"看到一致的 `expired_at`；若属有意，建议在代码注释中写明，并在文档标注该读取会阻塞同 run 的采集。

**建议修复**：若一致性可由 `expired_at` 单列判断，读取侧改为无锁读取 + 过期判断；否则保留但补充注释与容量说明。

## 三、已复核并撤销的候选问题（不要按这些修改）

以下 6 项在本次复核中被排除。它们要么是文档化设计，要么原判断有误；建议在后续修复时不要重复处理。

| 撤销项 | 原判断 | 复核结论与依据 |
| --- | --- | --- |
| 取消的实验显示 `completed` | 认为取消意向被抹掉 | **按设计**。[deployment-regression-20261011.md](../deployment-regression-20261011.md) 第 32 行"不新增实验 cancelled 终态。`completed` 表示调度结束"；[backend.md](../backend.md) 第 203 行"completed 公共终态不变"；[frontend.md](../frontend.md) 第 47 行"不能从实验'已完成'推断执行或评分通过"。取消事实由 CaseRun/Attempt 的 `cancelled`、`cancelled_runs` 与取消审计表达 |
| 清单版本复制整份 input/result 属缺陷 | 认为存储放大 | **按设计**。[backend.md](../backend.md) 第 199 行"已固定清单保存自己的执行结果副本"，第 207 行"后到事件或产物产生新清单，原评分继续引用原清单" |
| 评分取消被记成 error、指标虚高 | 认为与评分器故障混淆 | **error 是文档规定**（[platform.md](../platform.md) 第 157 行、[backend.md](../backend.md) 第 191 行、[coding-regression-review-proposal.md](../coding-regression-review-proposal.md) 第 245 行"当前 Runner/调度路径通常为 error"）。正常上报路径由 [service.py:480-486](../../src/eyes/server/scheduling/service.py#L480-L486) 转成 `skipped`；只有 Runner 失联才走 error。本文件仅保留 P2 的文案问题 |
| JSONL 末尾换行导致整批失败 | 认为常见故障 | **实测不成立**。`str.splitlines()` 会丢弃单个尾随换行，只有真正的空行才产生 `""` 并触发 422。严格拒绝空行符合 [AGENT.md](../../AGENT.md)"整体校验后发布，明确报告错误行，不静默丢弃无效记录" |
| `bootstrap` 重复执行会破坏本地观测 | 认为缺少保护 | 多项目时本地观测要求显式配置，[observation.md](../observation.md) 第 23 行已写明"多个项目需由服务端设置 `EYES_LOCAL_OBSERVATION_PROJECT_ID`，不会猜测目标项目"。属运维注意事项 |
| Scheduler 只捕获 `SQLAlchemyError` 属告警缺失 | 认为长期失败不可见 | 非 DB 异常会终止进程，由编排 `restart: unless-stopped` 拉起，属 fail-fast 选择；DB 异常每轮记录日志 |

## 四、未验证风险（需运行环境，不列为缺陷）

| 风险 | 位置 | 需要的验证 |
| --- | --- | --- |
| 大实验（接近 `max_experiment_runs=100000`）下创建比较报告可能超过前端 30 秒超时 | [comparison/service.py:24-49](../../src/eyes/server/comparison/service.py#L24-L49) 一次性加载两侧全部 CaseRun/Attempt/ScoreRun；[api.ts:30](../../frontend/src/api.ts#L30) `AbortSignal.timeout(30000)` | 真实 PostgreSQL + 10 万级实验，测量接口耗时与内存 |
| 索引缺失对查询计划的实际影响 | 见 P1 | `EXPLAIN (ANALYZE, BUFFERS)` 对比修复前后 |
| 取消与 rescore 并发路径的触发概率 | 见 P2 | 真实并发场景压测；当前仅为代码路径推断 |

## 五、已执行的检查与结果

以下为 2026-11-03 在本机实际运行得到的输出，非推测：

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 后端静态规范 | `uv run --no-sync ruff check src migrations integrations` | All checks passed |
| 后端格式 | `uv run --no-sync ruff format --check src migrations integrations` | 113 files already formatted |
| 后端语法 | `uv run --no-sync python -m compileall -q src migrations integrations` | exit 0 |
| 前端 lint | `npm run lint`（frontend） | 通过 |
| 前端格式 | `npm run format:check` | All matched files use Prettier code style |
| 前端类型 | `npx tsc --noEmit` | exit 0（未执行会写 `dist/` 的 `npm run build`） |
| PEP 758 语义探针 | 自建脚本 | `except TypeError, ValueError, AttributeError:` 实测同时捕获三种；`KeyError` 会漏出。该写法在 Python 3.14 合法 |
| JSONL 解析探针 | 自建脚本 | 单个尾随换行正常；真正空行触发 `ValidationError(json_invalid)` |
| 模型索引反射 | 自建脚本 | `WorkItem` 仅有 `ix_work_queue`、`ix_work_reservations`；`Project` 无索引、无 name 唯一约束 |

## 六、测试与 CI 现状（沿用，不在本轮修复范围）

- 仓库无测试资产：`src/**/test_*.py`、`frontend/src/**/*.test.tsx` 均为空。
- [ci.yml](../../.github/workflows/ci.yml) 只有 backend lint、migrations（真实 PostgreSQL 18.6 上 upgrade/downgrade/`alembic check`/readiness 冒烟）、frontend lint+format+build 三个 job，**没有 test job**。
- 按 [AGENT.md](../../AGENT.md) 的验证与修改纪律，未经用户明确要求不新增测试；因此上述修复只能依赖现有静态检查与人工/真实运行验证。

## 七、覆盖边界

- 只读审查，未修改任何文件；未启动 PostgreSQL / Docker / API / Runner / Scheduler。
- P1 的索引收益、P2 的并发触发概率、第四节的两项风险均为**基于源码与 schema 的推断**，未做 `EXPLAIN`、压测或故障注入。
- 前端结论来自源码阅读与既有 `tsc/eslint/prettier` 结果，未做浏览器运行验证。
- 未审查 `data/`、`MewCode/` 下的历史运行材料与私有产物。

## 八、建议修复顺序

1. **P1 索引 + 聚合查询**：收益最大、风险最低；注意同时改模型与迁移，依赖 CI 的 `alembic check` 兜底。
2. **P2 两处状态语义**：`sweep` 的取消文案、`claim()` 的 `cancel_requested` 守卫；改动小，建议放在同一提交内并附变更说明。
3. **P3 观测页增量拉取**与只读接口行锁：需要前端与 API 协同，建议先确认 `FOR UPDATE` 是否为一致性所需。
4. 修复后按风险运行对应检查；涉及 API/迁移时在 Docker Desktop Linux 容器 + PostgreSQL 上复验，并记录版本、命令与未覆盖边界（沿用 [10-22 维护记录](2026-10-22-remediation.md) 的记录格式）。
