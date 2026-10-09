# Eyes 开发与验收计划

校准日期：2026-10-09。依据当前源码、0001～0004 迁移、根目录 [开发约定](../AGENT.md) 与已有验证记录整理。本次仅做源码和文档核对，未执行 Agent、数据库迁移、测试、构建或故障注入；历史运行结果按原记录引用，不作为本次重新验证。未读取私有凭据或完整运行数据目录。

状态含义：**已实现**表示找到对应代码；**部分实现**表示设计中仍有实现缺口；**未实现**表示已明确保留为计划且未找到运行时实现；**无法确认**表示缺少足够运行证据。功能实现与里程碑验收分别判断，静态核对不能证明可靠性或容量。优先级 P1 为首版闭环/可信度阻塞，P2 为发布验收，P3 为后续扩展。

## 已完成的实现与证据

| 功能 | 实现状态 | 代码依据 | 验证边界 |
| --- | --- | --- | --- |
| 版本、JSONL 导入与实验快照 | 已实现 | `contracts/dataset.py`、`server/catalog/service.py`、`server/experiments/service.py`；0001 版本/快照保护触发器 | 整体错误行校验、幂等、同事务入队；多轮 steps 不在已完成范围 |
| HTTP/Python 接入与独立执行/评分进程 | 已实现 | `adapters/http.py`、`adapters/python.py`、`runner/process.py`、`runner/worker.py` | Python 真实闭环有记录；HTTP 通用代码不能替代真实 HTTP 目标验收 |
| 认证、项目与 Runner 范围 | 已实现 | `server/api/dependencies.py`、`server/admin.py`、`server/scheduling/service.py` | read/manage/runner 边界已有代码；完整权限验收仍待补齐 |
| 领取、执行/评分容量、租约、取消与未知额度保留 | 已实现 | `server/scheduling/service.py`、`server/storage/database.py` | advisory lock 与 SKIP LOCKED 协作；双 Python Agent 的峰值 3 任务和部分中断/取消有记录，完整故障矩阵未验收 |
| SDK、事件去重、产物上传与固定清单 | 已实现 | `sdk/recorder.py`、`server/evidence/service.py`、`runner/outbox.py` | MewCode 有真实事件/产物记录；缺失、迟到、耗尽、过期等分支未全面验证 |
| 规则/可信 Python 评分、证据等待、retry/rescore | 已实现 | `scorers/rules.py`、`server/evaluation/service.py`、0002 | 固定清单、引用/数值校验和历史保留有代码；重评分不自动替换最早评分汇总 |
| 固定回归报告、Web 与 CLI 门槛 | 已实现 | `server/comparison/service.py`、`contracts/comparison.py`、`cli/main.py`、`frontend/src/components/ComparisonCreate.tsx` | 默认首个成功 Attempt 的最早 ScoreRun；历史有 fail/inconclusive，真实同目标版本改善/退化及 gate pass 尚缺证据 |
| 多 Agent 批次 | 已实现 | `server/experiments/batches.py`、`contracts/work.py`、0004、`frontend/src/pages/Batches.tsx` | 原子分组、成员独立执行、派生状态与取消；不同任务集不合并质量通过率 |
| 被动观测与流程图 | 已实现 | `server/observation/`、`contracts/observation.py`、0003、`frontend/src/pages/Observation.tsx` | Deta exporter 真实接入及一次离线补传有历史记录；exporter 不在本仓库源码中，当前外部实现未重新审查 |
| Compose、审计、实验证据保留与备份恢复 | 已实现 | `deploy/compose.yaml`、`server/operations/service.py`、`server/operations/backup.py` | 历史 Compose 和无 ready 产物恢复已运行；含完整事件/产物/评分的恢复、容量仍待验收 |
| BUG-001～004 | 已实现，待验证 | Outbox 单项退避/孤立文件隔离、`LocalArtifactStore.check_ready`、Web 显式 ScoreRun 选择 | 保留现有 [故障修复计划](bug-fix-plan.md)，不重复建立修复清单；静态检查通过不等于行为验收 |

上述 Python 路径均相对于 `src/eyes/`，前端/迁移/部署路径相对于仓库根目录。

## 实现缺口与后续设计

| 功能 | 状态 | 当前事实与保留目标 | 优先级 |
| --- | --- | --- | --- |
| 普通契约严格要求版本字段 | 部分实现 | `contracts/base.py` 的 `schema_version` 缺省为 1.0，已拒绝其他版本与未知字段；[开发约定](../AGENT.md) 要求拒绝缺失版本。后续需制定兼容/迁移方式再修改，不能直接改变旧请求行为 | P1 |
| 重启后未知远端任务自动核对 | 部分实现 | 适配器有 cancel/reconcile，Runner 在有效租约期间调用；Scheduler 仅扫描、标 unknown 并保留额度，管理端 resolve 追加人工事实。缺少后台主动查询/重启后自动协调，不得自动重跑未知副作用 | P1 |
| 统一 Agent 协议客户端与参考服务 | 未实现 | [协议草案](agent-protocol.md)、`contracts/agent_protocol.py` 和 JSON Schema 已存在；Runner/适配器未引用该运行时协议，继续保留旧 HTTP/Python 接入。下一步落实发现、幂等提交、按键/状态查询、取消确认和证据交换 | P1 |
| 执行结束后的独立清理记录 | 部分实现 | Attempt 单独保存清理状态，但当前随执行最终结果上报；后续独立清理记录接口尚未实现，见 [后端说明](backend.md) | P2 |
| 被动观测自动保留清理 | 未实现 | observation 正文在 PostgreSQL JSONB；现有实验 Artifact 清理不覆盖这些表，需设计观测记录生命周期 | P2 |
| 多轮 steps 驱动 | 未实现 | `CaseDefinition.single_turn_only` 明确拒绝非空 steps；保留未来有序步骤驱动设计 | P3 |
| 模型代理、OTLP exporter/查询后端、共享产物存储 | 未实现 | 当前为 SDK/接口采集、可选 ConsoleSpanExporter 与 LocalArtifactStore；保留扩展目标，根据实际需求推进 | P3 |
| 任意用户代码沙箱、完整原生 Windows API/Runner | 未实现 | 可信 Python/独立进程不是安全沙箱；POSIX 进程组、resource 和目录 fsync 存在平台限制。沙箱是另行设计目标；是否支持原生 Windows 需先明确发布范围 | P3 |

## M0～M4 验收状态

| 阶段 | 当前状态 | 完整验收前必须补齐 |
| --- | --- | --- |
| M0 契约定稿 | 部分实现，未完整验收 | 四类契约、表/API/CLI 已存在；版本字段规则仍有规范差异，缺少真实 HTTP 与 Python 两种接入的完整逐项核对；统一协议还未替换旧运行时 |
| M1 真实闭环 | 实现主体已有，部分验收 | Deta/Zeta/MewCode 为 Python 接入记录；补齐真实 HTTP 的导入、执行、评分、证据、认证及独立接入复现 |
| M2 并发与恢复 | 部分实现、部分验收 | 已有多 Runner 峰值并发、受控工作进程中断和 unknown 额度保留；补齐 Runner 整体崩溃、网络/数据库异常、重传、停止确认、自动协调与隔离证据 |
| M3 回归产品 | 已实现，验收无法确认完整通过 | 列表/详情/固定报告/CLI 已有；同一真实目标版本的一次改善和一次退化、gate pass 及评分追溯仍待验证；不同 Agent 的通过率差异不替代版本回归 |
| M4 发布验收 | 工具已实现，验收无法确认完整通过 | 历史部署/迁移/无产物恢复已有；当前版本干净环境复现、权限、完整证据恢复、保留运维、依赖审计问题和容量/长期运行仍待验证 |

## 待验证任务

| 优先级 | 任务 | 验收输出 |
| --- | --- | --- |
| P1 | BUG-001～004 行为验收 | 按现有计划验证上传失败时其他项继续、崩溃孤立文件隔离、readiness 200/503、Web 选择新评分后新报告绑定且旧报告不变 |
| P1 | 真实 HTTP Agent 闭环 | 固定目标能力/版本，完成导入→执行→独立评分→证据查询与认证，并记录外部停止、幂等及查询的实际边界 |
| P1 | 多 Runner 故障恢复矩阵 | Runner 整体退出、API/网络/数据库中断、租约失效、重复/迟到上传；原始状态、额度、停止/核对证据与失败记录齐全 |
| P1 | 同目标真实版本回归 | 冻结同一测试集和评分口径，实际产生改善与退化；核对默认/显式评分选择、引用、分母和 gate 0/1/2/3 |
| P2 | 当前版本发布与完整备份恢复 | 干净环境升级到 0004；含 ready 产物、事件、清单、评分和报告的备份恢复及 audit，旧 Runner 凭据隔离、未知额度保留和权限边界可核对 |
| P2 | 证据生命周期与容量 | 真实等待截止/迟到/过期/回收、磁盘耗尽和采集丢弃；记录版本、环境、负载和测量方法，再给出容量说明；跟进 MewCode 记录中的依赖审计问题 |
| P2 | 仓库自动化测试基线确认 | `git ls-files '*test*' '*spec*'` 未返回测试文件，pyproject/frontend scripts 未定义测试入口；本次未找到已纳入 Git 的测试套件。后续按明确授权制定测试范围，已有冒烟数据集与评分器不等于仓库测试套件 |

## 下一阶段三个开发任务

1. **P1：落实统一 Agent 协议运行时与参考 HTTP 接入端。** 沿用已落地契约，保留旧接入兼容；用真实 HTTP Agent 补齐 M0/M1，不能以参考服务或模拟运行替代真实目标验收。
2. **P1：实现重启后未知任务的安全自动核对。** 在目标查询/停止/幂等能力允许时追加核对事实，未确认停止继续保留额度；结合 Runner 整体崩溃与网络异常验收推进 M2。
3. **P1：落实普通公共契约的显式版本要求及兼容迁移。** 先梳理旧请求/JSONL/Runner 的缺省版本用法，明确升级路径，再对齐开发规范并验证兼容行为。

已有四项修复应先完成行为验收；真实版本回归与完整备份恢复优先补证据，无证据前不预设需要新增功能。以上均为后续计划，本轮不执行开发或运行验收。

## 证据入口

- [Python/MewCode 真实闭环](mewcode-validation.md)：2026-10-09，3/3 执行、3/3 评分通过、53 条事件和 6 份产物；仅基础冒烟。
- [双 Python Agent 并发与中断](../integrations/zeta/README.md)：2026-10-08，两个 Runner、峰值 3 任务；取消不代表远端停止已确认。
- [历史平台与运维验证](platform-validation.md)：2026-10-03，PostgreSQL/Compose、固定报告、fail/inconclusive 及无业务产物恢复。
- [历史后端验证](backend-validation.md)、[Web 说明](frontend.md)、[被动观测](observation.md)：按日期阅读；本计划不覆盖原始失败和环境限制。
- [BUG-001～004 计划及检查记录](bug-fix-plan.md)：代码已实现，故障/浏览器行为待验收。
