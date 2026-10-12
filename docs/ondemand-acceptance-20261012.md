# 按需运行稳定性验收（2026-10-12）

日期使用 Asia/Shanghai；基线 `67d2195`、当前分支 `main`。用户明确 Eyes 按需启动使用，本轮取消 24 小时发布门槛；24 小时及多日运行为未来可选验证，不宣称全天候运行已验证。数据一致性、恢复、访问控制和评分可信度要求保持。M3/M4 其他缺口见 [PLAN](PLAN.md)。

## 隔离与真实材料

Windows 宿主机、本机 Docker Desktop Linux、既有锁定镜像 `eyes-clean-control:20261011`、Python 3.14.7、PostgreSQL 18.6、迁移 `0005_reconciliation`。API/Runner 只读挂载当前源码。开始时 Docker 引擎未启动；启动 Desktop 后核对原容器，无运行中的旧服务。新建 `eyes-ondemand-20261012` 网络及独立 pg/artifacts/runner 命名卷，PostgreSQL 55448、API 18070；没有启动 Agent、领取执行工作或模型请求，模型费用 0。

从已验证完整备份恢复独立项目副本；为保持真实归属，项目和历史业务 UUID 原样保留，仅存在本轮独立数据库命名空间内，不与原项目服务共用数据库、证据或状态卷。新签发 manage 和仅 score 类型 Runner 凭据，恢复副本的旧 Runner 凭据全部撤销。原备份数据库摘要先核对；原数据库/卷不写入。复制后权限为服务 UID 10001、目录 0700、文件 0600。

私有现场保存在 Git 忽略的 `data/ondemand-20261012/`：setup/cycle/readback/close 实际采集命令、响应、日志、前后摘要、样本、停止检查、数据库与卷均保留，不提交。没有新增或修改仓库测试、评测用例、fixtures、mocks、依赖或业务源码。

## 实际使用周期与一致性

完整主周期约 **16.84 秒**，首轮读取、评分及正常停止约 **8.37 秒**；按实际工作结束收尾，没有固定空转时长。启动 API/Scheduler/PostgreSQL，readiness 200 后启动 score-only Runner（execution_slots=0、score_slots=1、poll=2 秒）。读取真实实验列表、结果、三项事件和已有固定报告，通过公开 rescore 创建三项独立 ScoreRun，由原冻结 `deta_code` 评分器实际执行原 fix-mean / integer-cli / stable-unique 产物。三项均 completed/pass、**12/12 功能检查**，绑定原固定清单，三次工作心跳及完成上报均 HTTP 200，三份 journal 的 ack 均 acknowledged=true。

正常停止 Runner 后停止控制组件，全部退出 0；随后启动控制端、readiness 就绪后重启同一 Runner，读取同一结果、事件和固定报告，再正常停止，全部退出 0。

- 初始 20 Attempt、341 Event、47 ready Artifact、86 Manifest、25 ScoreRun、17 固定报告、62 WorkItem 的逐行 SHA-256 均未改变；只追加三个评分及对应工作，没有新增执行或报告。
- 停止前和重启后七张业务表全部现有行摘要一致；六个读取端点 JSON 规范化摘要一致，报告 content/digest 及评分 result/manifest_id 包含在逐行核对中。
- 证据卷全部文件摘要一致。补充只读启动后获取三项 Attempt 详情/清单，**8 份真实产物下载全部 200，大小和 SHA-256 与冻结元数据一致**；读取到已持久化的新评分，未重新评分。
- Runner 状态卷停止前/重启后 23 文件、68399 字节，逐文件摘要全部一致，三份完成 ack 保留。最终 audit=ok：47 ready、86 manifests、28 scores、problems=[]。
- 原两个 unknown/reserved=true 工作全行不变，没有释放额度；原四个 queued 执行工作未领取。本轮三个评分均 completed/unreserved，无新增 unknown 或未确认结果。

## 复用的恢复证据

直接核对并引用 [Runner 可靠性验收](runner-reliability-20261011.md) 的真实材料，不重复故障注入：BUG-001 单项失败继续发送及恢复后 pending=0；BUG-002 孤立内容隔离和正常配对摘要保留；整体 Runner 退出后的原键查询、竞争/查询接管、重复/迟到只应用一次、退避跨重启和 unknown 占额。原材料位于 `data/safety-acceptance-20261011/`、`data/runner-reliability-20261011/`。这些覆盖未被本轮文档变更或短评分补槽修复改变。

旧 Runner 凭据恢复隔离沿用 [完整备份恢复](backup-release-review-20261011.md) 的真实撤销/拒绝和权限证据，本轮副本再次查询确认全部旧 Runner revoked=true；旧领取者拒绝覆盖沿用可靠性记录。没有用新凭据冒充旧 Runner，也未再次制造响应丢失或磁盘故障。

## 有限资源样本与残留

主周期采集 **2 个资源/状态样本，样本跨度 3.48 秒**，并保存整个周期 API/Runner/Scheduler 日志。采集包括 Docker CPU/内存/BlockIO、宿主机剩余磁盘、数据库大小、工作队列/租约、当前 Runner 心跳年龄及真实 status outbox 计数。样本过少，不称峰值上限或长期趋势。

| 组件 | 本轮 CPU 样本最大 | 内存样本范围 |
| --- | --- | --- |
| API | 14.21% | 119.9～122.2 MiB |
| PostgreSQL | 3.18% | 92.2～92.51 MiB |
| Scheduler | 0% | 61.62 MiB |
| Runner | 45.88% | 38.67～53.47 MiB |

宿主机剩余磁盘最低 136270995456 字节（约 126.9 GiB）；两次数据库大小均 11507391 字节。Docker BlockIO 是累计计数，不作为磁盘延迟。当前 Runner 心跳采样最大年龄 0.79 秒；短评分的活跃租约未被每个资源样本完整捕获，真实工作心跳与完成日志用于交叉核对。状态采样及最终 status 的 pending/rejected/orphaned/corrupted/quarantined 全为 0，保留三个真实评分 journal 是预期机制，不能判泄漏。短时内存差异不判泄漏，也不据此宣称无泄漏。

最终收尾等待 Runner 注册就绪后检查实际容器进程，只有 Runner 主进程，没有评分子进程；随后 Runner/API/Scheduler/PostgreSQL 全部 exited/0，初始化容器 exited/0。再次逐行核对七张表与主周期停止前完全相同。宿主机无本轮 Python 采集进程，Docker 无运行容器。开始时的 95 个原容器按 ID/镜像/状态/挂载核对无变化；不把该身份核对称为原数据库逐字节核验。数据、卷、日志及失败现场不删除。

未发现正在运行的 24 小时采集或本任务后续自动检查；既有 soak 三次目录及采样保留，没有停止或取消其他任务。当前不执行旧文档中的 86400 秒手动命令。

## 保留的失败与限制

两个预检 SELECT 使用了不存在的 scores 表、reconciliation_attempts 列；尚未创建评分，清理又因 Runner 尚不存在而失败，控制端保持运行。修正采集查询后才完成主周期。这是私有采集脚本错误，不修改产品来迁就错误查询。补充下载查询首次错误引用顶层 size_bytes/sha256，随后 size 字段路径错误，失败均保留；最终按 Artifact.metadata_content 的实际契约读取成功。

补充脚本启动 Runner 后立即停止，留下 **137** 的真实失败：Docker events 显示 start 后约 **0.33 秒**发 SIGTERM，Runner 稍后才注册，30 秒后 SIGKILL。该次不算正常停止通过，未有 active 工作或新增业务。调整采集流程为等 Runner 注册就绪再停止，真实复验退出 0，业务摘要不变。没有证据表明已就绪 Runner 的停止逻辑缺陷；**启动早期、信号处理器安装前的停止仍有此限制**，不将复验解释成修复了任意启动阶段的信号处理。

本轮通过的是已就绪组件的按需完整使用周期。无需重复已通过的故障注入或为时长空转。长期趋势、启动早期立即停止的通用保障、活跃任务停止的全部目标能力、观测正向/第二个 Agent、真实改善/退化、其余故障/权限/生命周期及容量边界仍按相应材料限定；24 小时及多日运行仅为未来可选目标。历史短时增长、历史失败及其他发布要求保持，不宣称 M0～M4 全部完成。

本轮交付仅文档：`git diff --check` 和五份修改文档的本地链接存在性检查通过。未运行构建或仓库测试，因为没有产品代码变更；真实评分器检查属于产品评分运行，不替代仓库测试。提交与推送结果以最终 Git 输出为准。
