# 容量保护开发与真实材料副本检查（2026-10-13）

后续 Web 任务于2026-10-14在现有运行状态页交付，见[实现和实际页面验收](capacity-web-20261014.md)。下面开发轮次的无Web说明及后续独立“部分通过”均为历史，不改写为当时已实现；未覆盖磁盘/强杀分支保持。

后续 2026-10-14 独立复核判定**部分通过**：原始材料与隔离小额度复验支持 API/CLI 已覆盖行为，容量 Web 未实现及部分故障分支证据不足；原失败及边界保留，见[本轮复核](capacity-cancellation-review-20261014.md)。

Windows PowerShell、本机 Docker Linux、PostgreSQL 18.6，起点 Eyes `83e9c63`。本轮实现源码，不只更新文档；未修改外部 Agent、仓库测试、fixtures 或 mocks，未安装依赖、执行 Agent/评分器、调用付费模型、做 24h 实验或填满宿主机磁盘。

## 实现与计量

复用原 HTTP 请求上限、观测 64 KiB/批次限制、产物大小/SHA-256 校验、原去重/冲突/确认及维护规则。新增配置默认关闭：每项目已保留实验与观测事件的 PostgreSQL JSON 文本字节额度、产物文件系统实际 available bytes 最低余量，以及事件 warning 百分比。计量对象、错误码、并发锁/崩溃处理和升级方式见[运维说明](platform.md#容量保护与当前告警)。无数据库迁移，head 保持 0006。

事件额度由 API 事务提交前实际聚合确认，超额整个请求回滚。所有 API worker 的配置须一致，先停写再启用；全 API 数据库事务使用独立容量锁，不引入调度重构或预留表。产物发布用卷内 flock 覆盖测量与实际发布，使用块分配余量；没有持久空间预留。失败/进程结束释放锁，孤立/临时文件仍由真实可用空间计量与原回收机制处理。

管理员通过 `GET /v1/operations/capacity` 或 `eyes-ops capacity --project-id UUID` 查看当前用量、配置阈值、UTC 测量时间、状态与原因。告警按 scope/project 稳定 ID 返回当前集合，重复查询不追加记录，恢复后消失；不做持久告警历史、邮件/Webhook 或 Web 新面板。未知卷数据是 null，不显示成 0。

## 独立环境与真实材料

Docker 启动时 daemon 未运行，启动现有 Docker Desktop 后继续。原 `eyes-review-20261013-*` 卷保持只读源挂载，用已有镜像复制到 `eyes-capacity-20261013-pg` 与 `eyes-capacity-20261013-artifacts`，新建同名网络和 PG 容器；原所有服务继续停止。新 API 仅挂载当前源码，不启动 Runner、Scheduler、Agent，端口 18111～18120 为本轮顺序配置的副本服务，实际结束状态另保存。

控制库沿用真实 recovery release 数据；观测库沿用已恢复的 `eyes_observation_review`，A 原事件文本合计 1346 bytes（含过期残留与 running 前缀），B 为 41565 bytes。只注册明确标注 archive replay 的新来源，以原真实 trae detail 的事件正文/ID/sequence/occurred_at 回放；不是新活动 Agent 或执行故障证据。产物用原真实 130 bytes/SHA-256 文件，新 metadata 名明确 archival copy，不修改 Attempt 原结果或重新评分。

私有响应、归档副本身份、SQL 查询结果、下载文件、日志位于忽略目录 `data/capacity-20261013/`，不提交凭据/正文。操作使用 PowerShell 实际 HTTP 请求、PostgreSQL 查询及既有 eyes-ops，不新增验收脚本、测试框架或断言。

## 实际结果

| 操作 | 实际响应及持久数据 |
| --- | --- |
| 观测新增拒收 | A 用量 1346，quota=1347，真实首事件增长 530；507 `project_event_capacity_exceeded`，新 source 下 run=0，项目仍 102 event/1346 bytes |
| 并发额度 | quota=1876，两个独立来源并行发送同一真实首事件；一个 200、一个 507，实际 103 event/1876 bytes，没有越额 |
| 额度满重传 | 重传赢家原批次 200、原 event_id 被确认，实际 103/1876 不增加；额度1/历史277371的实验事件也返回原 duplicate 回执 |
| 实验新正文拒收 | 从原真实 span 生成明确标注 archival replay 的新传输 envelope，仅改变 envelope event_id/producer；quota=277372，增长587被507拒绝。352 Event/277371 bytes 保持，新 producer 行为0，不保存伪造 Agent 结果 |
| 原生去重 | 原真实 agent.event 仅换 envelope 标识仍200/duplicate=true，绑定既有 record，说明原生身份去重先于新增容量；没有将这种请求错误计为新增字节 |
| 配置恢复 | 增加观测 quota 后，原拒收首事件成功；不是重新执行 Agent |
| 清理恢复 | 回放某来源完整原51事件和终态；仅将该副本可信终态的服务端保留时钟调至10月10日。quota=2508时用量43441，另一归档来源首事件507；既有 maintain 清1 run/51正文后用量1978，同一请求200后实际155 event/2508 bytes。原 running 前缀与另一归档 running 保留，B51 event/41565 bytes保持 |
| 产物空间拒收 | 在独立卷设置最低余量2000000000000（高于实际free约1014GB），130字节上传507，pending保持；最终代码响应含8192 bytes块/目录分配余量，没有写成功后静默丢弃 |
| ready幂等 | 高空间门槛下原ready产物同字节PUT200，不重复发布；事件逻辑额度降为1也不破坏原产物确认 |
| 产物恢复 | 最低余量调回1048576后原pending PUT200/ready；授权下载130 bytes、SHA-256与原声明完全相同。最终服务用户audit：29 ready、51 Manifest、16 ScoreRun，status=ok/problems=[] |
| 告警与恢复 | near-limit为warning，超限/满额度与卷低余量为blocked；两次轮询同一稳定ID，没有新增告警行。恢复配置后alerts=[]；运维CLI同样返回实际用量/状态 |
| 未知值 | 指向不存在的测量目录，CLI返回unknown/volume_measurement_failed:2，used/free/total均null；不能用0表示未知 |
| 权限 | manage-A200，本项目用量；manage-B200且仅B用量；read-A403，来源令牌401。初次使用不匹配Runner归属访问事件403，无写入；改用原执行Runner后200/duplicate |
| 原执行事实 | 原17 Attempt、352 Event、16 ScoreRun、1 ComparisonReport、15 Resolution完整序列化内容相同；35 WorkItem与复制源的replica-after-pages快照一致。只有明确归档的两个产物登记及发布清单新增，不改原评分/报告/结果 |

清理时间调整只在本轮归档副本，不当作自然长期运行证据；清理1978 bytes包含历史过期残留，不声称数据库文件缩小。上述新实验 envelope 只用于被拒绝的传输验证，未产生新业务执行事实。

## 检查与操作失败

既有 Ruff check/format、Python compileall、git diff --check、Compose config、Alembic 全链离线 SQL 与真实 PostgreSQL alembic check（No new upgrade operations）通过；沿用已有镜像/依赖，没有构建新完整Compose或运行前端检查，因为未改前端。最终源码再核对错误处理位置并重启API验证空间拒收/恢复/下载和audit。

初次请求使用恢复Runner而不是原执行Runner，得到403，保留响应；切换原令牌后重复确认成功。初次想触发实验新增拒收却选到原生agent.event，原去重正确返回200，未持久化新envelope；换成明确归档span后验证507。SQL json_agg多行输出第一次直接逐行ConvertFrom-Json失败，改为完整文件读取；最初WorkItem比较使用更早的时钟快照出现差异，使用实际复制源replica-after-pages后0差异，不将旧核对时钟变化归于本轮。开发期Ruff导入/格式修正、文档补丁上下文不匹配及空间错误wrapper初次放错基类已修正；未把未实际触发的ENOSPC分支记作实测通过。

## 覆盖与限制

源码保护普通实验事件、公共/local观测、恢复事件，及LocalArtifactStore普通/恢复/修复发布。运行检查覆盖公共观测、普通事件、普通产物、权限、现有维护和运维状态；未独立触发local新增拒收、恢复事件新增拒收、恢复重建空间拒收或多进程产物竞争。数据库事务锁/卷锁有源码，但本轮未注入接收中强杀/取消、ENOSPC/EDQUOT、权限故障、满inode或慢盘，不宣称完整故障矩阵通过。

项目逻辑额度不覆盖数据库全部对象、prompt/metrics/结果/清单/评分/版本/审计元数据增长、索引/页/TOAST/WAL、日志、备份或其他进程；普通清理不保证PG文件缩小。产物最低余量只约束同一共享卷的参与发布者，无法保证其他进程不耗尽空间，不能代替文件系统硬配额或宿主机监测。事务聚合/串行化适合当前单团队按需规模，未验收大积压吞吐、长期趋势或原生Windows存储发布。未增加删除未知任务、未确认工作或活动记录的容量恢复路径。

本轮容器最终正常停止并保留独立卷及私有证据，原现场不删除；Commit与Push结果以交付输出为准。
