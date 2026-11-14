# Eyes 文档索引

首次部署从[项目 README](../README.md#docker-compose)开始。部署与运维命令以当前使用文档为准，带日期的记录说明各轮使用的版本、验证范围和结果。

## 当前交付与后续工作

| 文档 | 内容 |
| --- | --- |
| [投入使用前任务审核 · 2026-11-14](Review/2026-11-14-release-readiness.md) | 交付判断、当前版本复验、已知问题及七类验收余项 |
| [开发与验收计划](PLAN.md) | 当前交付范围、后续路线和 M0～M4 完整验收条件 |
| [Windows 设计待办](TODO.md) | 接入引导、状态表达、审阅和观测流程图 |
| [仓库开发约定](../AGENT.md) | 架构、Windows 环境、修改与验证要求 |

## 使用与维护

| 我想做什么 | 文档 |
| --- | --- |
| 部署控制端、配置数据库、管理令牌 | [后端与 API](backend.md) |
| 使用控制台、前端开发与部署 | [Web 控制台](frontend.md) |
| 接入 Agent、配置 Runner、接入可信评分器 | [Agent 接入与 Runner](agent-integration.md) · [MewCode 接入](../integrations/mewcode/README.md) · [Deta 接入](../integrations/deta/README.md) |
| 接入统一 HTTP 协议 | [统一 Agent 协议](agent-protocol.md) · [HTTP 运行时](agent-http-runtime.md) |
| 批量评测多个目标 | [多 Agent 批次](multi-agent-batches.md) |
| 收集和清理被动观测数据 | [被动观测](observation.md) |
| 建立编码回归测试集与评分口径 | [编码回归扩展](../integrations/coding/README.md) |
| 生成固定报告、执行 CLI 门槛 | [回归与 CLI](platform.md#1-固定回归报告与-ci) |
| 查看取消审计、核对远端未知任务 | [取消审计](cancellation-audit.md) · [未知任务恢复](unknown-recovery.md) |
| 配置容量保护、升级、备份和恢复 | [运维手册](platform.md) |
| 理解模块和公共契约 | [架构](architecture.md) · [控制契约 Schema](control-contracts-v1.schema.json) · [Agent 协议 Schema](agent-protocol-v1.schema.json) · [契约版本迁移](contract-version-migration.md) |
| 核对 Web 样式依赖的来源与许可 | [shadcn CSS 说明](../frontend/src/vendor/README.md) |

## 验收与维护记录

### 最近复验和修复

- 2026-11-11 [第一阶段维护复验](Review/2026-11-11-maintenance-validation.md) · [MewCode 真实版本回归复验](mewcode-regression-20261111.md)
- 2026-11-03 [项目复核与待修复清单](Review/2026-11-03-eyes-project-review.md)
- 2026-10-21 至 10-22 [项目审查](Review/2026-10-21-eyes-project-review.md) · [逐项修复记录](Review/2026-10-22-remediation.md)
- 2026-10-18 [前端依赖修复与 Docker 验证](dependency-fix-20261018.md)
- 2026-10-17 [缺陷修复计划](fix-plan-20261017.md) · [Docker 与 API 复验](fix-verification-20261017.md)

### 部署、恢复、容量和取消

- [干净部署、独立接入与权限验收](clean-deployment-permissions-20261011.md)
- [完整证据备份恢复](backup-release-review-20261011.md) · [按需运行稳定性](ondemand-acceptance-20261012.md)
- [Runner 可靠性与故障恢复](runner-reliability-20261011.md) · [原操作证据恢复](evidence-recovery-20261013.md) · [旧 Runner/outbox 与冻结插件兼容](contract-compatibility-validation.md)
- [容量与短时测量](capacity-validation-20261011.md) · [容量保护](capacity-protection-20261013.md) · [容量 Web 展示](capacity-web-20261014.md)
- [取消持久审计](cancellation-audit-20261014.md) · [容量与取消联合复核](capacity-cancellation-review-20261014.md)
- [故障处理与回归操作修复](bug-fix-plan.md) · [部署安全头与版本回归](deployment-regression-20261011.md)

### Agent 接入和观测

- [统一 HTTP 运行时验证](agent-http-validation.md) · [MewCode 真实评测](mewcode-validation.md) · [MewCode Windows 验证索引](../MewCode/README.md) · [Windows 重跑报告](../MewCode/2026-10-11-rerun/REPORT.md)
- [MewCode 与 trae 主动接入、并发与恢复](dual-agent-acceptance-20261012.md)
- [trae 被动观测与补传](observation-trae-acceptance-20261012.md) · [被动观测生命周期](observation-retention-20261013.md)

### 编码回归专项

- [数据集与评分方案](coding-regression-review-proposal.md) · [实施记录](coding-regression-implementation-20261016.md) · [评分器修复](coding-scorer-fixes-20261016.md)
- [评测准备](coding-regression-preflight-20261016.md) · [trae 首轮真实评测](coding-regression-real-acceptance-20261016.md)
- [订单第二次真实评测](coding-regression-order-real-r2-20261016.md) · [订单 unknown 专项核对](order-unknown-investigation-20261016.md)

### 独立验收汇总

- [前三个开发任务验收审查](acceptance-review-20261011.md) · [后续三轮独立验收](acceptance-followup-20261011.md)
- [按需运行、被动观测与双 Agent 独立复核](acceptance-followup-20261012.md)
- [恢复与观测生命周期独立验收](acceptance-review-20261013.md)
