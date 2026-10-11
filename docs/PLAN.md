# Eyes 开发与验收计划

初次校准日期：2026-10-09。依据当前源码、0001～0004 迁移、根目录 [开发约定](../AGENT.md) 与已有验证记录整理；该次仅做源码和文档核对。2026-10-10 仅更新统一 Agent 协议运行时任务：实现与静态检查完成，Docker 恢复后真实 MewCode HTTP 基本闭环已验收，见[检查及实际记录](agent-http-validation.md)。其他历史结果按原记录引用，不作为本次重新验证。

状态含义：**已实现**表示找到对应代码；**部分实现**表示设计中仍有实现缺口；**未实现**表示已明确保留为计划且未找到运行时实现；**无法确认**表示缺少足够运行证据。功能实现与里程碑验收分别判断，静态核对不能证明可靠性或容量。优先级 P1 为首版闭环/可信度阻塞，P2 为发布验收，P3 为后续扩展。

2026-10-11 本轮验收审查：前三项均为**部分通过**。统一 HTTP 基本闭环及已记录版本兼容子集通过；安全自动核对代码已实现，但活动 Runner 整体崩溃/查询失败/竞争/迟到/退避重启的真实故障证据仍缺。直接复核既有私有 API 记录得到 HTTP 3/3、旧完成重传 6 个 duplicate 确认、原执行/清单/历史评分相同；没有重新执行 Agent。后续独立 0005 实际迁移已有日志，不能代替未知任务恢复验收。本轮 Docker Linux 引擎不可达，M0～M4 不升级为完整通过。源码位置、提交、证据层级及待验证项见[验收审查](acceptance-review-20261011.md)。

2026-10-11 后续 Runner 可靠性轮次：审查 #3/#5 本地恢复缺口、#6 评分基础设施错误已修复并推送；独立真实材料核实及新故障运行完成安全恢复指定必需门槛、BUG-001～004。详见 [修复、验收与剩余边界](runner-reliability-20261011.md)。以上环境阻塞是原审查记录，不再表示这些必需场景完全缺证据；本轮未开展版本回归/备份恢复，M2 全面验收仍保留其他矩阵。

## 下一阶段顺序

1. **已完成本轮指定门槛：安全恢复必需项、Runner 可靠性修复及 BUG-001～004。** 原操作不重跑、unknown 占额、可信终态只释放一次、竞争/迟到/持久化退避已有独立真实证据；补齐坏载荷隔离和评分错误分类的实际运行，其他 M2 矩阵保留。
2. **P1：同一真实目标版本改善/退化回归。** 固定既有测试集/评分口径，核对报告、默认/显式评分、分母和 CLI gate。
3. **P2：当前版本完整证据备份恢复。** 包含 ready 产物、事件、清单、评分/报告及 unknown 额度，在独立恢复环境核对摘要、权限和 audit。

三个可直接启动的提示词见[审查交付](acceptance-review-20261011.md#可直接使用的三个提示词)。HTTP 可选正向能力、真正缺版本历史材料和其他旧客户端仍保留下面待验证计划；不因上述顺序而取消。下一轮是验收与必要修复，尚不能宣称发布完成。

## 已完成的实现与证据

| 功能 | 实现状态 | 代码依据 | 验证边界 |
| --- | --- | --- | --- |
| 版本、JSONL 导入与实验快照 | 已实现 | `contracts/dataset.py`、`server/catalog/service.py`、`server/experiments/service.py`；0001 版本/快照保护触发器 | 整体错误行校验、幂等、同事务入队；多轮 steps 不在已完成范围 |
| HTTP/Python 接入与独立执行/评分进程 | 已实现 | `adapters/agent_http.py`、`adapters/http.py`、`adapters/python.py`、`runner/process.py`、`runner/worker.py` | Python 真实闭环及 2026-10-10 MewCode 统一 HTTP 3/3 执行与独立评分有记录；不能推广为全部可选/故障能力已验收 |
| 认证、项目与 Runner 范围 | 已实现 | `server/api/dependencies.py`、`server/admin.py`、`server/scheduling/service.py` | read/manage/runner 边界已有代码；完整权限验收仍待补齐 |
| 领取、执行/评分容量、租约、取消与未知额度保留 | 已实现 | `server/scheduling/service.py`、`server/storage/database.py` | advisory lock 与 SKIP LOCKED 协作；当前 Windows 环境的双 Agent 并发、中断、取消和完整故障矩阵仍需验收 |
| SDK、事件去重、产物上传与固定清单 | 已实现 | `sdk/recorder.py`、`server/evidence/service.py`、`runner/outbox.py` | MewCode 有真实事件/产物记录；缺失、迟到、耗尽、过期等分支未全面验证 |
| 规则/可信 Python 评分、证据等待、retry/rescore | 已实现 | `scorers/rules.py`、`server/evaluation/service.py`、0002 | 固定清单、引用/数值校验和历史保留有代码；重评分不自动替换最早评分汇总 |
| 固定回归报告、Web 与 CLI 门槛 | 已实现 | `server/comparison/service.py`、`contracts/comparison.py`、`cli/main.py`、`frontend/src/components/ComparisonCreate.tsx` | 默认首个成功 Attempt 的最早 ScoreRun；历史有 fail/inconclusive，真实同目标版本改善/退化及 gate pass 尚缺证据 |
| 多 Agent 批次 | 已实现 | `server/experiments/batches.py`、`contracts/work.py`、0004、`frontend/src/pages/Batches.tsx` | 原子分组、成员独立执行、派生状态与取消；不同任务集不合并质量通过率 |
| 被动观测与流程图 | 已实现 | `server/observation/`、`contracts/observation.py`、0003、`frontend/src/pages/Observation.tsx` | 当前 Windows 环境的 exporter 接入及离线补传仍需验收；exporter 不在本仓库源码中，当前外部实现未重新审查 |
| Compose、审计、实验证据保留与备份恢复 | 已实现 | `deploy/compose.yaml`、`server/operations/service.py`、`server/operations/backup.py` | 历史 Compose 和无 ready 产物恢复已运行；含完整事件/产物/评分的恢复、容量仍待验收 |
| BUG-001～004 | 已实现，待验证 | Outbox 单项退避/孤立文件隔离、`LocalArtifactStore.check_ready`、Web 显式 ScoreRun 选择 | 保留现有 [故障修复计划](bug-fix-plan.md)，不重复建立修复清单；静态检查通过不等于行为验收 |

上述 Python 路径均相对于 `src/eyes/`，前端/迁移/部署路径相对于仓库根目录。

## 实现缺口与后续设计

| 功能 | 状态 | 当前事实与保留目标 | 优先级 |
| --- | --- | --- | --- |
| 普通契约严格要求版本字段 | 已实现，部分实际兼容验证 | Contract 默认要求显式 schema_version，更新本仓库生产端；显式兼容窗口固定截止 2026-11-01T00:00Z，历史/outbox 保留原载荷和摘要。实际 API/JSONL/幂等已验证；Docker 恢复后补齐 6 个已接受结果的旧 Outbox 网络确认及两个冻结插件/旧 SDK 组合各 3/3 评分、12/12 检查。真正缺版本载荷及其他旧客户端仍待验证，见[补充记录](contract-compatibility-validation.md) | P1 |
| 重启后未知远端任务自动核对 | 统一 agent_http 已实现，真实故障验收阻塞 | 2026-10-11 独立只读查询租约、原键/Attempt/run 校验、不可变来源记录、数据库退避、重传/迟到隔离及可信终态释放额度；0005 兼容历史 unknown。通用 HTTP/Python 不推断可靠查询能力，仍需人工 resolve。Docker/API/Agent 不可达，本次没有真实故障验收，见[恢复说明及未验证项](unknown-recovery.md) | P1 |
| 统一 Agent 协议客户端与参考服务 | 已实现，真实基本闭环已验收 | 2026-10-10 `adapters/agent_http.py`、`agent_service/http.py`、Runner/领取匹配、发现发布与兼容校验，保留旧 HTTP/Python。真实 MewCode 3/3 执行/评分通过、12/12 功能检查、48 外部事件及 8 产物对应、认证/去重/已完成服务重启核对；可选能力正向及活动故障矩阵未覆盖，见[记录](agent-http-validation.md) | P1 |
| 执行结束后的独立清理记录 | 部分实现 | Attempt 单独保存清理状态，但当前随执行最终结果上报；后续独立清理记录接口尚未实现，见 [后端说明](backend.md) | P2 |
| 被动观测自动保留清理 | 未实现 | observation 正文在 PostgreSQL JSONB；现有实验 Artifact 清理不覆盖这些表，需设计观测记录生命周期 | P2 |
| 多轮 steps 驱动 | 未实现 | `CaseDefinition.single_turn_only` 明确拒绝非空 steps；保留未来有序步骤驱动设计 | P3 |
| 模型代理、OTLP exporter/查询后端、共享产物存储 | 未实现 | 当前为 SDK/接口采集、可选 ConsoleSpanExporter 与 LocalArtifactStore；保留扩展目标，根据实际需求推进 | P3 |
| 任意用户代码沙箱、完整原生 Windows API/Runner | 未实现 | 可信 Python/独立进程不是安全沙箱；POSIX 进程组、resource 和目录 fsync 存在平台限制。沙箱是另行设计目标；是否支持原生 Windows 需先明确发布范围 | P3 |

## M0～M4 验收状态

| 阶段 | 当前状态 | 完整验收前必须补齐 |
| --- | --- | --- |
| M0 契约定稿 | 部分实现，未完整验收 | 四类契约、表/API/CLI 已存在；普通版本显式要求已落实并有部分真实 API 兼容记录，旧客户端/重传场景和两种接入完整逐项核对仍待验证；统一 Agent protocol_version 保持独立 |
| M1 真实闭环 | HTTP/Python 基本闭环已验收，独立复现仍待验证 | 当前 Windows 环境的 MewCode Python 及统一 HTTP 均有基础闭环记录；HTTP 导入、执行、独立评分、证据和基础认证已补齐，干净环境独立接入及完整能力核对未覆盖 |
| M2 并发与恢复 | 部分实现、部分验收 | 已有多 Runner 峰值并发、受控工作进程中断和 unknown 额度保留；补齐 Runner 整体崩溃、网络/数据库异常、重传、停止确认、自动协调与隔离证据 |
| M3 回归产品 | 已实现，验收无法确认完整通过 | 列表/详情/固定报告/CLI 已有；同一真实目标版本的一次改善和一次退化、gate pass 及评分追溯仍待验证；不同 Agent 的通过率差异不替代版本回归 |
| M4 发布验收 | 工具已实现，验收无法确认完整通过 | 当前版本干净环境部署复现、权限、完整证据恢复、保留运维、依赖审计问题和容量/长期运行仍待验证 |

## 待验证任务

| 优先级 | 任务 | 验收输出 |
| --- | --- | --- |
| 已通过 | BUG-001～004 行为验收 | 既有独立真实故障/浏览器结果及持久化绑定已核实；当前 Runner 健康补传、readiness 无残留、新默认报告保持最早选择通过，见 Runner 可靠性验收 |
| P1 | 真实 HTTP Agent 扩展能力与故障验收 | MewCode 基本闭环已完成，保留未覆盖的取消/资源正向路径、第二个统一协议实现、响应丢失及活动故障矩阵；记录停止、幂等和查询的实际边界 |
| P1 | 多 Runner 完整故障恢复矩阵 | 指定必需的整体退出、原操作查询、竞争/重复/迟到、退避跨重启、unknown 占额与终态只释放一次已核实；其他能力/故障组合继续保留，不把子集通过视为完整 M2 |
| P1 | 同目标真实版本回归 | 冻结同一测试集和评分口径，实际产生改善与退化；核对默认/显式评分选择、引用、分母和 gate 0/1/2/3 |
| P2 | 当前版本发布与完整备份恢复 | 干净环境升级到 0005；含 ready 产物、事件、清单、评分和报告的备份恢复及 audit，旧 Runner 凭据隔离、未知额度保留和权限边界可核对 |
| P2 | 证据生命周期与容量 | 真实等待截止/迟到/过期/回收、磁盘耗尽和采集丢弃；记录版本、环境、负载和测量方法，再给出容量说明；跟进 MewCode 记录中的依赖审计问题 |
| P2 | 仓库自动化测试基线确认 | `git ls-files '*test*' '*spec*'` 未返回测试文件，pyproject/frontend scripts 未定义测试入口；本次未找到已纳入 Git 的测试套件。后续按明确授权制定测试范围，已有冒烟数据集与评分器不等于仓库测试套件 |

## 原前三个开发任务及历史记录

1. **P1：统一 Agent 协议运行时与参考 HTTP 接入端已实现，真实 MewCode HTTP 基本验收完成。** 用户补充允许参考服务实际调用 MewCode；Docker 恢复后本轮完成导入、3/3 执行/独立评分、证据/认证/去重及终态重启核对，保留首次部署失败。完整可选能力/活动故障与多实现验收未覆盖，见[实际记录](agent-http-validation.md)。
2. **P1：重启后未知任务的安全自动核对已实现，真实故障验收阻塞。** 2026-10-11 支持统一 agent_http 原操作只读查询，未确认终态继续保留额度；0005 迁移、来源历史、独立查询令牌和持久化退避已实现。静态检查及离线 SQL 生成通过，Docker Linux 引擎及历史 API/Agent 不可达；Runner 整体崩溃、网络/API 恢复、多进程竞争及实际 PostgreSQL 升级均待隔离真实环境验证，M2 未完整通过，见[恢复说明](unknown-recovery.md)。本任务不开始后续普通契约版本迁移。
3. **P1：普通公共契约显式版本及兼容迁移已实现，部分实际验证。** 2026-10-11 严格版本、有限窗口、生产端及历史边界已落实。实际 API/JSONL/同键重放、6 份真实 journal 投影已验证；随后补齐严格 Linux API 上的旧 Outbox 中断/恢复及两个旧 SDK/冻结插件组合，历史保持不变。其他旧客户端、真正缺版本载荷及完整故障矩阵仍待验证，见[补充记录](contract-compatibility-validation.md)。

已有四项修复、真实版本回归与完整备份恢复保留原计划。2026-10-11 前一任务完成第 2 项实现，真实故障验收阻塞；本任务只推进第 3 项，未扩展其他功能，未改写已有历史实验、摘要或评分数据。完整旧客户端/重传验收仍待真实环境完成。

## 证据入口

- [统一 HTTP 运行时真实验收](agent-http-validation.md)：2026-10-10，Docker 阻塞解除，真实 MewCode 3/3 执行和独立评分、12/12 功能检查、60 条 Eyes 事件/8 产物、认证/去重/终态服务重启核对；完整可选/故障矩阵未覆盖。
- [Python/MewCode 真实闭环](mewcode-validation.md)：2026-10-09，3/3 执行、3/3 评分通过、53 条事件和 6 份产物；仅基础冒烟。
- [BUG-001～004 计划及检查记录](bug-fix-plan.md)：代码已实现，故障/浏览器行为待验收。


2026-10-11 前一任务：安全自动核对已实现并同步文档，0005 离线 PostgreSQL SQL、ruff 和字节编译检查通过；Docker Linux 引擎与历史 API/Agent 不可达，真实故障验收阻塞，M2 未完整通过。该任务当时未开始普通契约版本迁移。详见[恢复记录](unknown-recovery.md)。本次版本迁移另在独立本机 PostgreSQL 实际运行 0001～0005 迁移及 API 兼容操作，不能替代前一任务的 Runner 崩溃/网络恢复验收。
