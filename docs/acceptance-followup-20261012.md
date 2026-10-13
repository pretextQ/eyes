# 按需运行、被动观测与双 Agent 独立复核

后续更新：2026-10-13 已完成原操作证据恢复源码修复及两原故障任务的无重跑复验，含新清单、明确清理事实、显式原评分器及补传整体退出/过期租约续传。见[新记录](evidence-recovery-20261013.md)。本页 partial/unknown/评分不足结论保留为 2026-10-12 的历史事实。

复核日期：2026-10-12（Asia/Shanghai）。Eyes `9a71587`，trae-agent `7f24fc2`；复核前两个工作区干净，HEAD 均与本地 origin/main 引用一致。本轮只读审查相关实现、提交及本机私有原始材料，不启动服务、不发模型请求、不安装依赖、不增加测试或业务功能。没有重新执行故障注入或浏览器验收。

## 结论与范围

| 任务 | 独立复核结论 | 依据与限制 |
| --- | --- | --- |
| 一：按需启动、使用、停止与重启 | 通过已就绪组件的本轮范围 | 三个原证据重评分 completed/pass，reserved=false；重启前后数据库快照和六个公开读取摘要相同，8 份产物下载记录均 200、大小/摘要一致。启动早期立即停止的 137 记录仍保留，不宣称任意启动时刻都可正常退出 |
| 二：trae 被动观测 | 通过本轮指定场景 | 3 个真实 run、100 事件；两个 completed、一个真实限额 limited，均 complete、sequence_gaps=0；40 份具名权限响应与矩阵一致，51 个离线原始事件与服务端 content 完全相同，三次重启快照一致。强杀 exporter、缓冲满及磁盘故障仍未验收 |
| 三：主动接入、双目标并发与恢复 | 正常闭环及定向恢复通过，完整故障证据/评分恢复部分通过 | 三组正常结果各 3/3 执行成功、3/3 有效评分通过；15 份原始下载重新计算大小/SHA-256 全匹配；成员准备失败隔离成立。原 Attempt 恢复 succeeded，但 evidence_status=partial、cleanup_status=unknown，故障批次有效评分未补齐 |

24 小时及多日实验不是当前按需用途的验收要求。以上通过不代表 M0～M4 全部通过，也不把不同 Agent 的结果当作同一 Agent 版本改善/退化。

## 原始材料复核

- 任务一：`data/ondemand-20261012/`。初始快照包括 20 Attempt、341 Event、47 Artifact、86 Manifest、25 ScoreRun、17 报告、62 WorkItem、2 unknown；停止前与重启后的完整快照相等。三个新评分均 completed/pass、未占额。最终 pending/rejected/orphaned/corrupted/quarantined 为 0，retained_work=3 是保留的评分 journal，不当作泄漏。
- 任务二：`data/observation-trae-20261012/`。逐项比较 40 个矩阵项与同名响应文件，状态和响应内容均一致；51 个原始 payload 按 event_id 与实际持久事件 content 比较，无差异。before-restart、after-restart、after-exporter-restart 三份完整快照相同。数据库实际计数 experiments/case_runs/attempts/work_items/score_runs/runners 全部 0，observed_runs=3、observed_events=100，证明被动路径独立。
- 任务三：`data/dual-agent-20261012/`。正常批次 trae/MewCode 与修正 trae 的实际结果均 3/3 成功、3/3 pass。重新读取 15 份 `.bin`，逐项比对 Artifact.metadata_content，大小和 SHA-256 全部一致。失败隔离使用修正部署后的 failure-network 响应：trae 三项准备失败、MewCode 三项执行/评分通过；早期 queued 材料没有当作通过。
- 双目标并发以真实 Agent 边界事件重新计算，三个重叠区间约 6.376948、3.859175、6.149320 秒；不使用平台排队状态推断。
- 恢复后的原 Attempt 保留原 remote_operation_id，Resolution.content 中 applied=true 只有一次；两次重复核对均 duplicate=true。断网修正前后记录、重启查询证明原 unknown run 不变，stopped_confirmed=false、completed_at=null，新提交 429，未把模型通信异常当作停止确认。预算三个正常账本合计 66 次调用、约 ¥0.07688112，无未确认 usage 或预留；本轮没有新费用。
- 双目标停止前/重启后的完整历史快照相同。正常退出、预期强杀与启动早期失败的退出码沿用已有实际记录，本轮未重新启动容器验证。

## 实现与静态检查

定向阅读 trae 的真实 loop、ModelClient/预算、HTTP 接入、direct CLI、SQLite exporter 和进程清理。它有独立消息/模型/工具循环，仅复用 Eyes 协议外壳；未导入 MewCode 业务循环。HTTP 未确认请求保留 unknown 的修正与实际材料相符。取消、资源上传、环境隔离继续按 false 能力处理，工具清理仍是 best-effort。

Eyes 的本轮业务变更只有 Observation 页面两处来源文案。当前前端 `npm run typecheck`、该文件 Prettier 检查通过；trae `ruff check src/trae_agent` 通过，五个本轮相关文件的格式检查通过。**全目录 `ruff format --check src/trae_agent` 未通过**：当前锁定 Ruff 0.17.0 要求调整 runtime.py:49、tools.py:172 的 except 元组格式。这是格式交付问题，未修改源码，也不能写成本轮全量格式通过。没有重新运行完整构建或仓库测试。

## 尚需收口

1. 优先补齐 unknown 核对成功后的原执行证据、清理事实和独立评分；当前只恢复调度结果，不能声称完整证据闭环恢复。
2. 同步当前入口文档：根 README 仍两处写被动观测待验收，backend 当前状态仍写双 Agent/观测正向待验证；trae IMPLEMENTATION 的历史“接入未开始”段应显式标为历史并链接最新 EYES_ACCEPTANCE，保留历史事实。
3. 收口上述两个格式问题；强杀/缓冲满/磁盘故障、支持取消/资源的真实目标、观测生命周期及真实版本改善/退化仍按 PLAN 保留，不为 24h 空转重复已通过场景。

相关实际运行记录：[按需周期](ondemand-acceptance-20261012.md)、[被动观测](observation-trae-acceptance-20261012.md)、[双 Agent](dual-agent-acceptance-20261012.md)、[开发计划](PLAN.md)。本轮新增本复核报告，不修改业务代码或其他文档，不提交或推送。

## 同日文档与格式收尾

上述复核完成后，用户授权更新 README、后端说明及新 Agent 两个文件并提交推送。Eyes README/backend 已同步被动观测、双目标与按需运行的实际验收范围，保留故障证据/清理/评分缺口；trae runtime.py/tools.py 仅按当前 Ruff 修正 except 元组格式。修正后 trae 全目录 `ruff check` 和 `ruff format --check` 通过，两仓库差异检查及上述 Eyes 文档共 59 个本地链接存在性检查通过。trae IMPLEMENTATION 历史段落本次未修改；真实版本改善/退化和其他验证缺口仍保留。此前格式失败记录作为历史保留，不改写为首次检查通过。两仓库按本次授权分别提交、推送，结果以 Git 输出为准。
