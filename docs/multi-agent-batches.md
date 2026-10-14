# 多 Agent 批次

一个批次可包含 1–32 个 Agent 目标版本。每个成员独立选择测试集、评分器、任务并发、超时和重复次数；也可以复用相同测试集进行对照。一个目标版本在同一批次只能出现一次。不同版本若属于同一个 Target，仍共享该 Target 的容量。

2026-10-11 已在真实项目通过单成员 Web 批次创建、比较选项及时更新及排队取消核对，见[验收记录](deployment-regression-20261011.md)。这是关联入口的定向验证，不能代替多 Agent 并发/隔离或版本改善/退化验收。

## 使用流程

1. 在「目标 Agent」发布各 Agent 的真实接入配置和能力；在目标所在环境配置 Runner 的 Python 入口或 HTTP origin。接入清单不是仅选择一个全局 Agent，Runner 可注册多个入口，也可以部署多个 Runner。
2. 发布各成员所需的测试集和评分口径。
3. 打开「多 Agent 批次 → 创建批次」，逐个选择 Agent、测试集、评分口径和任务并发数，然后一次入队。
4. 批次详情显示每个成员的排队、运行、未知、执行成功和额度占用；「查看任务」进入原有实验的用例、评分、证据和单独取消流程。可从成员实验返回所属批次。
5. 「取消整个批次」在同一事务内请求取消各成员。已结束成员保持原结果；执行中任务仍需确认停止，unknown 仍可能保留额度。

一个用例的一次重复对应一个任务。例如 Agent A 的测试集有 10 个用例、重复 2 次、并发 3：它计划执行 20 个任务，最多同时执行 3 个。Agent B 可以选择另一份测试集并配置并发 2。两者可并行调度，合计申请 5 个执行槽位，实际并发受其余容量约束。

## 调度与隔离

批次只组织多个独立实验；每个成员保留自己的固定快照、CaseRun、Attempt、证据、评分和历史。任务仍由现有 PostgreSQL 工作表与 Runner 领取，不新增消息中间件，也不让一个 Agent 负责拆分或代跑其他 Agent 的任务。

- 单成员的活动额度受实验 `concurrency` 和目标 `concurrency_limit` 约束。
- 项目执行额度、全局执行额度、符合能力与凭据范围的 Runner 槽位进一步约束总并发。
- 执行与评分使用不同额度及 Runner 槽位。配置 `execution_slots` 与 `score_slots` 时按宿主机和外部服务实际承载能力设置；默认均为 1。
- 任务存在但没有匹配入口、允许 origin 或凭据范围的 Runner 时，保持排队；创建成功不代表 Agent 已实际执行。
- 并发大于 1 要求真实具备会话与环境隔离。Deta 当前已发布接入声明环境未隔离，容量仍为 1，本功能不修改这个声明。
- Runner 按既有队列顺序领取，不保证所有成员同时启动或严格公平分配。只有足够的匹配 Runner 槽位和共享额度，多个成员才会同时执行。
- 结果未知不表示目标已经停止；该任务保留的额度不会被批次创建或取消绕过。

不同任务集、评分器的质量结论分别展示，批次不把它们合成一个通过率。成员实验可继续参与既有可比性检查和回归报告。

## API 与 CLI

新增接口，原单 Agent 实验接口及 Runner 协议保持兼容：

- `POST /v1/experiment-batches`：需要 manage 令牌和 `Idempotency-Key`。
- 批次顶层和 experiments 中的每个 ExperimentCreate 都要求显式 `schema_version: "1.0"`；旧请求的有限窗口及文件迁移见[版本迁移](contract-version-migration.md)。
- `GET /v1/experiment-batches?limit=50&offset=0`：分页读取批次摘要。
- `GET /v1/experiment-batches/{id}`：批次快照、各成员实验与任务进度。
- `POST /v1/experiment-batches/{id}/cancel`：请求取消全部成员；可选理由和请求键，响应追加父级审计及 duplicate，成员逐一记录真实处理结果，见[取消审计契约](cancellation-audit.md)。

创建 body 的 `name` 为批次名称，`experiments` 为现有 `ExperimentCreate` 请求组成的数组；每个对象提供自己的 `target_version_id`、`dataset_version_id`、`scorer_version_ids`、`concurrency` 等配置。每个成员默认超时 300 秒、重复 1 次、证据等待 60 秒，选择首个执行成功的 Attempt。

创建在单事务中完成：所有成员合法后一起提交，任一成员无权访问、超容量或无效时整体回滚。相同项目与请求键、相同参数返回原批次；同键不同参数返回 409。整个批次的用例数乘重复次数之和也受 `EYES_MAX_EXPERIMENT_RUNS` 限制，不能按成员拆分绕过限制。

```sh
# batch.json 为上述批次请求，使用已发布版本的真实 UUID。
eyes create-batch --file batch.json --key release-check-20261008
eyes batches
eyes batch <batch-id>
eyes wait-batch <batch-id> --deadline 600 --interval 2
eyes cancel-batch <batch-id>
```

`wait-batch` 等待所有成员调度结束：未解决执行或等待超时返回退出码 2，配置/API 错误为 3；完成返回 0 不等于所有评分通过，质量门槛仍使用已有回归报告与 `eyes gate`。

## 数据升级

新迁移为 `0004_experiment_batches`，在 `0003_observation` 后增加批次表与可空的 `experiments.batch_id`。旧实验保持独立且可读取，不回填为批次，不覆盖历史快照。

0004 是引入批次时的历史迁移编号；当前部署必须升级到 head `0007_cancellation_audit`，不能停在 0004 运行当前服务。后续普通 schema_version 严格要求与旧请求窗口见[版本迁移](contract-version-migration.md)，升级需核对控制端、Scheduler、Runner 的实际安装版本。

先按现有运维流程备份并停止控制端/调度器，再执行 `uv run alembic upgrade head`，随后以当前代码重启控制端和调度器。Runner 协议未变化，可以继续使用已有配置。API 就绪检查要求迁移达到当前 head。

降级到 `0003_observation` 会移除批次分组元数据，保留成员实验及任务；需要保留批次关联时先备份，不应把降级当作无损操作。
