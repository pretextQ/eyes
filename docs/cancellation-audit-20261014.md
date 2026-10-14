# 取消持久审计开发与独立验收（2026-10-14）

后续再次独立读取原始材料、比较完整快照摘要，并在新卷复核重启同键读取/read权限/追加保护，结论为**通过本轮范围**，不升级活动远端停止或基础设施故障矩阵，见[独立复核](capacity-cancellation-review-20261014.md)。本记录历史操作与失败保持。

计数更正：原记录将0007备份审计总数写为十条；完整SQL JSON及备份前后列表实际均为十一条，完整文件SHA-256一致。恢复API的十条是分页响应，不能作总数。本轮据原材料更正下表，未发现记录丢失，不改写历史操作失败。

日期为 Asia/Shanghai；起点 `f4f97ba`（容量保护已独立提交、工作区干净）。Windows PowerShell / 本机 Docker Linux；宿主 Python 3.14.4，缓存控制镜像 Python 3.14.7，PostgreSQL 18.6。此次交付实际源码、0007 迁移、契约/schema、CLI 与 Web，不修改评测用例、评分器、Runner/外部 Agent 或容量保护实现。

## 实现范围

两个公开入口均通过 `server/experiments/cancellation.py` 处理；原调度取消成为内部 `_cancel`，无审计的批次取消函数移除。取消与追加审计同事务；批次父请求和每个成员处理关联保留。身份来自认证 Credential，理由可选且有长度/展示限制，传输键按凭据作用域去重。read/manage 可项目分页查询，Runner 不可查询或取消。数据库拒绝 UPDATE/DELETE，备份包含原记录，恢复和重评分不改写。字段、查询、失败、重试、保留及对象删除规则见[功能契约](cancellation-audit.md)。

## 独立材料与操作

原 `eyes-review-20261013-*` 服务保持停止，PostgreSQL/产物源卷只读挂载复制到 `eyes-cancel-20261014-*` 新卷、网络和 PG。当前源码以只读 bind 挂载缓存 `eyes-clean-control:20261011`，没有重建完整部署镜像。副本没有启动 Runner、Scheduler、Agent 或评分进程；不发起模型请求、付费调用、24h 实验或远端停止。

控制副本复用原双 Agent 项目 `2fb02d3f-a313-41de-a973-423d8e743079` 的真实目标、三任务测试集及原评分器配置，公开 API 创建明确用于审计检查的排队实验/双成员批次。这些只是排队操作，不产生 Attempt，不作为 Agent 活动或远端停止证据。

原 2026-10-11 `backup-final`（0005）另恢复到 `eyes_audit_old_restore`，含两项原真实 unknown/reserved 工作；随后升级到 0007。另一个同备份副本只升级到 0006，用 Git `f4f97ba` 的完整原 src 快照及原工具制作真实 0006 备份，再用当前工具恢复、升级至 0007。源备份没有修改。

私有 HTTP/CLI 响应、身份、SQL 输出、备份失败目录、截图及运行日志位于忽略目录 `data/cancellation-20261014/`；不提交凭据或原请求/证据正文。新 PostgreSQL 客户端使用本机已有 PG 18.6 容器的原二进制和共享库；没有新增声明依赖。首次 `uv run` 自动同步了已有 Python 环境并改写锁文件，锁文件已恢复基线；后续使用现有 `.venv`，不提交依赖变化。

## 真实结果

| 检查 | 实际结果 |
| --- | --- |
| 旧无 body 实验入口 | 原已结束 `12a6667e-bdf1-47fe-8caf-82b488ef4f44` 200；reason=null、already_finished，原 succeeded/评分及调度结果保持 |
| 排队实验取消 | 新 `55c940a4-271e-4d49-add6-520b02bdd3a9`：queued→completed，3 CaseRun/WorkItem cancelled，无 Attempt、无占额；审计 processed，前后计数真实保存 |
| 传输重复 | 同对象/理由/键重复 200、duplicate=true，共用 `e5ff68f4-7056-401a-84fd-4f8ba4f89f5e`，没有新增审计或重新处理 |
| 混合成员批次 | `800173e4-b432-4951-b1ec-c3cd6405ce91`：一个成员先取消结束，整批取消父请求记录 already_finished=1/processed=1；两子记录关联父 `4ce0dc56-084c-4c4f-bfc2-7f282febd684`。整批同键重传复用父记录，不新增成员历史 |
| 同键并发 | 两个 PowerShell 并行真实 POST，均 200、同 `d027176e-06f2-4a69-ab62-e2c655921f08`；一个 duplicate=false、另一个 true，数据库只一条处理记录 |
| 独立重复并发 | 两个不同键均 200/duplicate=false，分别追加 `0c80b4b4-a220-405c-9d0b-619061b877ec`、`e5e499a1-700d-4a35-98d9-c5339413345d`，已结束对象均 already_finished |
| 原真实未知任务 | `caa6d1b5-176d-4b30-a854-ebbb53b5b6fa` 的原 Attempt `ab066e63-ef6f-44ab-bb76-0b9d38135af8` 保持 unknown，reserved=1；只取消另外两项排队工作，实验 completed_with_unresolved，下一独立请求 already_finished。两原 unknown Attempt 的整行 JSON 前后完全相同 |
| 权限与项目隔离 | read/Runner 取消 403；Runner 查询 403；read 查询 200，可 limit=2/offset=1；另一项目查询 200/空历史（当时未操作），跨项目取消 404并在该调用者项目保存 failed，不泄露目标事实 |
| 无效参数 | 同键变理由 409；伪造 actor_id 字段 422；reason 1001 字符 422；拒绝前置请求不写管理操作审计 |
| 理由与客户端 | 已结束对象的独立合法请求追加历史；常见令牌样式理由保存为三个 [redacted]。CLI 带 reason/key 实际请求与重传 duplicate=true；HTML 样式理由在 Web 作为字面文本显示 |
| Web 实际提交 | `e68a3a92-b245-4163-ba23-da5602d53e68` 经浏览器弹窗输入理由并提交；页面立即 completed、3 cancelled、Attempt=0，审计显示经认证的凭据 UUID、服务端时间、理由及平台处理结果 |
| Web 关联与布局 | 实验事实可展开，批次父记录按需展开真实两个成员及 parent_id；390/1280 宽度检查，修正初版 notice 横向布局，长 ID/理由换行，事实使用既有可滚动 JsonBlock |
| 重启 | 两副本 API 实际 restart 后持久审计可读取；原 unknown/预留没有被审计替代为停止确认 |
| 0007 备份往返 | Linux `eyes-ops backup /deliver/verified-0007` 27 ready 产物，空目标 restore/audit 为 ok：49 清单、16 评分；备份时十一条审计的完整整行 JSON（含键摘要、理由、身份、时间、结果、父关联）完全相同，恢复 API 200读取前十条（该分页响应不等于备份总数）。此后 CLI/理由/Web 操作只在源副本追加，未混称为备份时内容 |
| 旧备份兼容 | 0005 原备份恢复 audit=ok，47 ready/86 清单/25 评分，两项 unknown 保持；0006 实际备份也由当前 restore 完整恢复同份材料，再升级 0007、alembic check 无差异。未补造旧取消身份/时间/理由 |
| 追加与迁移保护 | 实际 UPDATE/DELETE 事务均被 PostgreSQL immutable trigger 拒绝；非空审计 downgrade 拒绝，head/历史保持；空新库 0007→0006→0007 成功 |
| 原历史保持 | 控制副本原17 Attempt 整行 JSON 前后完全相同，仍16 ScoreRun；新排队操作没有执行或评分。原审计备份十一行全字段一致，后续合法请求只追加 |

结束前控制库共14条审计（含两个批次子行及其他项目失败行）：processed=6、already_finished=6、failed=2。旧故障备份副本另有原 unknown 操作和其重复/权限失败记录，不能与主项目数量混算。

## 静态与迁移检查

已有 Ruff check/format、Python compileall、前端 lint/format:check/build（包含 TypeScript）、git diff --check 通过。全链 Alembic 离线 SQL、新空 PostgreSQL 全链 upgrade、0005/0006 真实材料升级、当前 PostgreSQL alembic check 均通过；实际 JSON Schema/OpenAPI 包含可选 CancellationRequest。Compose config 只作配置核对，不宣称新完整部署闭环。

没有新增、修改测试文件、fixtures、mocks、自测脚手架或评测口径；以上为手动真实 HTTP/CLI/数据库/浏览器操作和既有静态/迁移工具。

## 操作失败与限制

首个批次请求重复同一目标被原契约 422 拒绝；之后改用两个已有真实目标。一次 unknown 操作使用错误项目凭据得到 404/failed 审计，随后以正确项目凭据进行真实检查；没有伪造管理身份。初期 PostgreSQL 连接使用错误本地密码失败，切换私有环境配置继续。

备份尝试保留失败结果：缓存控制镜像缺 pg_restore，旧备份 bind 权限对服务用户不可读；Windows 原生 backup 目录同步报 OSError，其输出不作为完成备份。新卷路径、Linux 原工具及已有 PG 客户端使正式备份/恢复完成；Docker cp -L 首次 symlink 路径错误，改按 PG readlink 的实际文件复制。缺 deploy/.env 的首个 Compose config 请求失败，随后使用已有样例配置核对。开发期导入/格式、Empty props 与分页/窄屏布局修正后检查通过；没有把静态/失败尝试计为运行通过。

未新增活动 Runner 的取消确认、Agent 远端停止正向、活动评分停止或部分成员领域失败注入；no_change/partial_failure 的保护分支为源码检查。原 unknown 是既有真实故障备份，不能称作本轮新活动故障。没有注入审计 insert/commit 时磁盘满、进程强杀或数据库中断；同事务回滚保证来自实际 PostgreSQL 事务结构，不能将普通并发核对扩大成全部失败矩阵。对象/项目/凭据删除后的独立 ID 保留为源码规则，未实际删除原真实材料；数据库所有者防篡改、实名操作者、自动审计过期、总容量硬配额和分页快照均未实现。

原现场保持不变，本轮服务最后正常停止并保留独立卷和证据。Commit/Push 的实际哈希与结果以交付报告为准。
