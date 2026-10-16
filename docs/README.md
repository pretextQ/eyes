# Eyes 文档导航

状态同步：2026-10-14（Asia/Shanghai），汇总各轮实际验收记录；运行方法和范围以对应记录为准。开发与修改约束见 [AGENT.md](../AGENT.md)，当前任务和里程碑以 [PLAN.md](PLAN.md) 为准。带日期的验收文档保留对应轮次的版本、失败与未覆盖项，不能将其中的历史环境阻塞直接当作当前状态。

当前约定范围交付完成，进入单团队自托管、按需使用与维护阶段；源码基线 `6929b6d`。原始 M0～M4 全条件及未覆盖分支不宣称通过，未来目标以 [PLAN](PLAN.md#当前交付状态与维护安排) 为准。最新补齐见[容量 Web 验收](capacity-web-20261014.md)与[容量/取消审计独立复核](capacity-cancellation-review-20261014.md)。

2026-10-13 证据入口：[恢复与观测生命周期独立验收](acceptance-review-20261013.md)，含原材料重新计算及新副本幂等/冲突/恢复补查。

## 当前证据与剩余工作

| 范围 | 当前结论 | 证据 |
| --- | --- | --- |
| MewCode Python / 统一 HTTP | 真实基础执行、独立评分与证据闭环通过；同一个 Agent 的两种接入，不等于两个不同 Agent 全能力验收 | [Python](mewcode-validation.md)、[HTTP](agent-http-validation.md) |
| 安全恢复必需项及 Runner 修复 | 整体退出、原操作只读查询、竞争/重复/迟到、退避跨重启、unknown 占额与可信终态只应用一次已有真实证据；坏载荷隔离及评分基础设施错误分类通过指定场景 | [可靠性验收](runner-reliability-20261011.md) |
| BUG-001～004 | 单项上传退避、孤立文件隔离、readiness 发布探测及 Web 历史评分选择行为条件通过 | [修复记录](bug-fix-plan.md) |
| nginx 与比较选项缓存 | HTML/assets 安全头经真实 HTTP 验证；普通/批次创建的新实验及时进入比较选项 | [部署与回归验收](deployment-regression-20261011.md) |
| 同一 Agent 不同版本回归 | 原样 MewCode `9282caa` / `3f10408` 各 3/3 执行和评分通过，正反向均无变化；历史选择、引用、分母、旧报告和 CLI 0/1/2/3 已核对 | [真实版本结果](deployment-regression-20261011.md#同一真实-agent-的不同版本) |
| trae 被动观测 | 直接用户任务、API 暂停保留/恢复补传、40 个权限/去重/冲突请求及真实页面核对通过本轮范围；不依赖实验/Runner | [接入验收](observation-trae-acceptance-20261012.md) |
| 容量保护与当前告警 | 逻辑正文额度、产物卷余量门槛及管理 API/CLI 已有定向证据；运行状态页只读 Web 已补齐，故障矩阵和数据库物理硬上限仍不在通过范围 | [容量独立复核](capacity-cancellation-review-20261014.md)、[Web 验收](capacity-web-20261014.md) |
| 取消操作审计 | 实验/批次认证身份、时间/理由、父子处理结果、事务、权限、追加保存和恢复通过本轮范围，不等于远端停止 | [使用说明](cancellation-audit.md)、[验收](cancellation-audit-20261014.md) |
| 被动观测保留 | 默认不清理，项目范围、有界短事务、过期审计及 API/Web 语义；独立真实材料副本清理 3 run/100 事件正文，重复执行、权限、归档前缀保护及数据库恢复通过指定范围 | [生命周期验收](observation-retention-20261013.md) |
| 干净部署与权限 | 冻结依赖构建、完整控制 Compose、新环境 HTTP 三任务闭环和 131 份具名权限请求通过本轮范围；trae 观测正向另有本轮证据，其他接入/权限组合仍缺材料 | [部署与权限](clean-deployment-permissions-20261011.md) |
| 完整证据备份恢复 | 47 ready 产物及事件/清单/评分/报告/unknown 占额在独立空目标恢复；全行摘要、字节、引用及服务用户权限复验通过本轮范围 | [恢复与发布风险核查](backup-release-review-20261011.md) |
| 有界容量与持续运行 | 真实证据重评分和读取、报告锁竞争、心跳/资源短时采集已有结果；补槽等待已最小修复。按需启动/停止/重启一致性已验收；执行容量、大报告/积压/慢盘未覆盖，24 小时和多日窗口为未来可选验证 | [环境、实测和限制](capacity-validation-20261011.md) |
| 当前用途与原始 M3 / M4 条件 | 原证据/评分恢复与观测生命周期分别通过当前范围，未发现必须追加的开发任务。用户决定改善/退化不纳入当前验收，未来有真实可比材料时再验证；24h 同为未来可选。原始 M0～M4 仍未全面通过，取消/资源、其他故障/容量目标保留 | [本轮独立验收](acceptance-review-20261013.md)、[计划](PLAN.md) |

实验 completed 表示调度结束，取消事实由用例/尝试及 cancelled_runs 展示；实验/批次取消请求现已提供独立追加审计及项目范围分页读取，见[取消审计](cancellation-audit.md)与[独立验收](cancellation-audit-20261014.md)。CLI 1/2 的本轮真实条件来自排队取消，不是版本质量退化。首轮源码遮蔽运行保留并排除版本验收，详情见部署与回归记录。M0～M4 均未宣称全面通过。

## 按任务查阅

| 任务 | 文档 |
| --- | --- |
| 理解模块边界与交付目标 | [架构](architecture.md)、[计划](PLAN.md) |
| 启动控制端、认证与公开 API | [后端](backend.md) |
| 接入目标、SDK、评分器与 Runner | [通用接入](agent-integration.md)、[统一协议](agent-protocol.md)、[HTTP 运行时](agent-http-runtime.md) |
| 首批编码回归与订单第二次评测 | [准备](coding-regression-preflight-20261016.md)、[首轮](coding-regression-real-acceptance-20261016.md)、[订单第二次及后续收尾](coding-regression-order-real-r2-20261016.md)；unknown及费用预留保留，无质量评分；专用组件已停机，待供应商事实 |
| 查询未知任务与恢复原操作 | [恢复操作](unknown-recovery.md)、[Runner 可靠性](runner-reliability-20261011.md) |
| 备份恢复与发布性能风险 | [平台操作](platform.md)、[完整恢复及 #7/#8/#10/#11 核查](backup-release-review-20261011.md) |
| 配置容量保护、查询当前告警 | [容量操作](platform.md#容量保护与当前告警)、[真实材料副本验收](capacity-protection-20261013.md) |
| 升级普通契约、旧载荷与客户端 | [版本迁移](contract-version-migration.md)、[兼容验收](contract-compatibility-validation.md) |
| 使用 Web、历史评分与固定报告 | [前端](frontend.md)、[平台与 CLI](platform.md) |
| 创建批次与被动观测 | [多 Agent 批次](multi-agent-batches.md)、[观测](observation.md) |
| 阅读原前三个任务的历史审查 | [验收审查](acceptance-review-20261011.md) |
| 阅读后续三轮的独立复核 | [最新验收结论与证据](acceptance-followup-20261011.md) |
| 查询语言无关契约 | [控制契约 Schema](control-contracts-v1.schema.json)、[Agent 协议 Schema](agent-protocol-v1.schema.json) |

当前开发宿主机为 Windows / PowerShell，API 与 Runner 在本机 Docker Linux 容器运行。具体接入与本机重启参考 [MewCode 说明](../integrations/mewcode/README.md)。原始载荷、凭据、数据库、组件日志和私有产物留在忽略目录；公开文档只记录必要版本、方法与结论。

- [按需运行验收（2026-10-12）](ondemand-acceptance-20261012.md)：独立真实材料重评分、正常停止/重启、历史/报告/证据一致性与残留核对。
