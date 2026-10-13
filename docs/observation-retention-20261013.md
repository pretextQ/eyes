# 被动观测生命周期交付（2026-10-13）

基线 `9755432`，Windows PowerShell、本机 Docker Linux，PostgreSQL 18.6；使用既有锁定 `eyes-clean-control:20261011` 依赖镜像、只读挂载本轮源码/迁移，Web 挂载本轮生产构建。不宣称无缓存镜像重建或原生 Windows API 支持。没有新模型调用、Agent 任务、实验、Runner、评分或 24h 运行；没有新增/修改测试、fixtures、mocks 或 snapshots。

## 源码与操作

0006 增加 terminal_received_at、run/event expired_at、expiration_summary 和两个保留索引。复用 `eyes-ops maintain`，支持默认预览、`--apply`、`--project-id` 和 `--observations-only`；复用已有 Compose maintenance profile 每小时运行。默认保留期 0，启用必须指定项目；每批 run/event 默认 20/500，每轮最多 10 批，各批独立提交，处理范围与上限见[观测说明](observation.md#观测保留与清理)。

仅明确终态且 terminal_sequence 存在的任务可过期，以服务端终态接收时间/最后事件接收时间较晚者为基准，不信任 producer occurred_at。running/disconnected 不过期，撤销来源也不证明停止。先标记过期、清 prompt、保留审计摘要，再有界清空 content，保留事件身份/序号/原 digest/接收时间；过期后立即阻止 API/Web 读取原正文，重传 410。来源写入令牌不获得任何删除能力，CLI 是可信部署者数据库操作。

## 独立副本及真实材料范围

Docker 引擎最初未运行，启动本机 Docker Desktop 后，确认原 `eyes-observation-20261012-pg` 为 stopped。把原 PostgreSQL 命名卷**只读**挂到一次性复制容器，复制到新 `eyes-retention-20261013-pg` 卷，原 API/Web/PG 均未启动、迁移或修改。新网络、新 PG/API/Web/maintenance 容器；宿主机端口 55453/18091/18092，原现场保留 55449/18071/18087。私有证据位于忽略目录 `data/observation-retention-20261013/`，不提交凭据、dump、事件正文或日志。

副本实际为原 trae 3 个终态 run、100 事件。为了让项目/未结束保护具有非空材料，用既有 51 条原始事件在项目 B 的来源做归档回放，用同一原始序列前 2 条在 A 的新来源 `archive-prefix-protection (not a live Agent)` 做未结束归档回放。事件正文、ID、序号、发生时间均原样，没有合成事件、模型/工具输出或新业务执行。归档回放仅证明这些真实事件副本及未结束存储状态的规则，不冒充第二次真实 Agent 执行或当前活跃 Agent。

B 的归档终态及 A 的未结束前缀只在副本调整服务端接收时钟到 2026-10-10，形成明确超过 1 天的非空保护对象，不修改原事件事实。原 3 run 的接收时间在 2026-10-12，自然到期。首次失败演练中的原样重传刷新了一个副本 run 的 last_seen_at；修复后将该副本接收时钟恢复为原快照值再执行，并记录操作，不把人为时间推进当作长期运行证据。

## 实际运行结果

| 操作 | 实际结果 |
| --- | --- |
| 迁移兼容 | 真实副本 0005→0006→0005→0006；修正事件不可变触发器后重新完成降/升；历史原正文保留，alembic check 无新增差异 |
| 默认关闭与预览 | retention=0 的显式 apply 不标记/清空新记录；retention=1 缺项目退出 3。run/event/max_batches=1/7/1 预览仅报告 1 run、7 event；预览前后两观测表全行 MD5 完全相同 |
| 小批次执行 | 同样 1/7/1 限制，实际标记 1 run、清空 7 event；已提交过期摘要，不要求该 run 全部事件在同一事务清空 |
| 后续排空 | 默认上限后续标记 2 run、清空 93 event；合计原 3 run 的 prompt 清空、100 event content={}、expired_at 非空；原终态/metrics/身份/序号/摘要保留 |
| 重复执行 | 再次 apply 标记 0 run、清空 0 event；前后两观测表全行 MD5 一致，清理时间/摘要不被重写；最终增加 batch_limit_reached 输出后再次执行仍 0/0 |
| 项目及未结束保护 | B 终态 51 事件、A running/disconnected 2 事件的 run/event 全行 MD5 前后分别一致。A 列表显示 disconnected/partial；没有真实新活动 Agent，因此不称活动进程故障验收 |
| API | A read/manage 详情/列表 200；过期详情 evidence_status=expired、prompt=null、events=[]、has_more=false。B read/manage 读 A 404，B 列表保留本项目归档。来源 read 401，read 创建来源 403，来源创建/撤销来源 401，跨项目撤销 404；DELETE run 405（没有删除接口）。原过期事件重传 410，不存在 UUID 404 |
| Web | 项目 read 连接实际新 API，清理前真实 51 事件流程图，轮询后正文/图形消失。最终 bundle 列表明确“观测内容已过期”，详情“内容已过期”、清理时间/51 事件摘要、“历史统计不代表现有完整证据”。390×844 和 1280×900 检查过期提示可读；截图/页面文本保留 |
| 自动维护入口 | 同现有 deployment 命令 `eyes-ops maintain --apply --interval`，独立容器用 1 秒间隔实际连续多轮，无新调度系统；均 0/0，无实验产物。Compose profile 配置通过检查；未宣称新镜像完整 Compose 无缓存部署 |
| dump/恢复 | 清理后 pg_dump custom/no-owner/no-privileges，在同独立 PG 实例的新空数据库 eyes_restored 单事务 pg_restore；head=0006，run/event 全行 MD5 与清理后源一致。此处为观测数据库真实恢复，不代替完整平台文件卷/所有备份生命周期验收 |
| 清理后降级 | 0006→0005 明确拒绝，数据库仍为 0006，防止删除过期标识后旧 API 误认为证据完整；旧完整正文只能从清理前备份恢复新的空目标 |

原 100 条事件 content 的 PostgreSQL `octet_length(content::text)` 合计从 77950 到 200（每个 `{}` 2 字节）。这是逻辑正文长度，不是 PostgreSQL 数据目录/TOAST/WAL 的物理回收量，更不是硬容量上限。另一项目 51 事件正文仍为 41565 字节，A 未结束前缀仍为 1146 字节。

## 失败与检查分层

首次 Windows 读取旧私有 JSON 时缺 UTF-8 参数、旧响应外层未解包，两次脚本停止在写入操作之前；修正读取后继续。首轮 apply 遇到 0003 `immutable_record` 触发器拒绝事件更新，当前批事务完整回滚；修正 0006 触发器为“仅已过期 run 下不可逆 content={} 转换，身份/摘要不可变”后通过真实执行。开发中的早期 0006 不含新函数，首次用修订版 downgrade 报 missing function；事务回滚，加入 DROP FUNCTION IF EXISTS 后完整降/升通过。首轮失败日志、矩阵和 PostgreSQL 日志保留，不改写为通过。

首次 `uv run` 意外尝试依赖同步，下载阶段中止，撤回其 uv.lock 变化；后续使用已有 `.venv/Scripts/ruff.exe` 和 Python、已有 frontend node_modules/依赖镜像，没有继续安装依赖。首轮 Ruff 提示行长/导入，格式化及修正后通过。

静态检查为 Ruff check/format、Python compileall、前端 ESLint/Prettier、tsc+Vite build、git diff --check、Compose config、Alembic 离线 SQL；实际迁移另有 PostgreSQL 升降级和 alembic check。上述检查不代替表格中的真实副本 HTTP/清理/恢复/浏览器结果。没有仓库自动化测试命令或新增测试材料。

首次停止 interval 维护容器退出 137：既有循环未处理 PID 1 的 SIGTERM。补齐 SIGTERM/SIGINT 后完成当前轮退出、interruptible interval wait，Compose maintenance 增加 3 分钟停止宽限；独立容器重新运行/停止退出 0。原 137 与复验日志均保留。关闭本轮 API/Web/PG/maintenance 容器并保留卷、数据库、dump 和日志。未做 down -v、删除原现场或重跑原 Agent。

## 兼容性和剩余目标

入站协议仍为 1.0，历史事件不要求增加字段。出站 run 摘要增加终态接收时间、过期时间和清理摘要，evidence_status 增加 expired；API 和 Web 一起升级到 0006。旧客户端须识别 expired/空 events，不得按原 metrics.events 推定正文存在。数据库触发器保护原事件不可变语义，仅开放保留清空；降级边界和备份恢复详见[平台说明](platform.md#观测迁移与备份恢复)。

保留审计元数据、活动/失联记录、备份和客户端副本不等于全项目擦除；已有下载副本不能远程撤回。超限拒收、数据库硬容量配额、空间告警、可信人工停止确认及审计/备份独立保留尚未实现。大积压并发清理、锁竞争/强杀中断、磁盘耗尽、生产规模迁移及长期趋势未在本轮实测；SKIP LOCKED/超时/批次上限有实现，不推广为性能或完整故障矩阵验收。M3/M4 其他缺口与未来可选长期运行继续保留在 PLAN。
