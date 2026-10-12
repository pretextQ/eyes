# trae 被动观测接入验收（2026-10-12）

当前基线 Eyes `88ffb2b`、trae `22fcb3f`，Windows 宿主机、本机 Docker Linux，按需运行。使用既有第二个 Agent `D:\woker\trae`，模型 `mimo-v2.6-flash`，没有创建新 Agent、实验、测试集、评分器或 Runner，也未运行双 Agent 并发。

## 实际发现与最小修复

trae 已有独立模型/工具循环和统一 Agent HTTP events，未有被动 observation exporter 或直接 CLI 入口；新增接入在 trae 仓库，直接实时监听原循环边界，绝不转换历史主动评测事件。

Eyes 实际真实页面将 trae 详情底部标成“事件来自 Deta”，无正文时也给出 Deta 专用配置提示。仅修正这两处详情文案为当前 Agent/当前观测接入，不改变来源身份、项目读取范围、状态、协议或图形配对。frontend lint、定向 Prettier 检查、类型检查/生产构建通过；第一次 format:check 提示该文件格式，格式化后通过。使用本轮实际 Web 加载修正后的 bundle，read 身份读取真实 completed/51 事件详情，浏览器确认“事件来自当前 Agent”。首版失败截图/文本保留，不据文案修复重跑业务。

## 已完成的真实链路

新网络 `eyes-observation-20261012`；PostgreSQL 55449、API 18071、Web 18087。新数据库/证据卷、两个 bootstrap 项目 A/B、A 的两个独立来源及 B 的来源；trae 运行状态与 exporter 状态卷均独立，来源令牌仅用于本来源 events/heartbeat 写入。API 为当前 Eyes 源码只读挂载及既有锁定控制镜像；新库实际迁移到 `0005_reconciliation`。没有 Scheduler/Runner 或主动工作。

用户授权本轮最多 ¥1。trae 调用前预算预留缺口已修正并发布 `c80287a`：持久化保守文本请求预留，未确认花费/账本损坏拒绝继续，不自动重试可能已付费的模型请求。凭据存在，实际通道 `https://api.xiaomimimo.com/v1`，两次直接用户任务实际调用 MiMo，累计已确认金额 ¥0.009092、11 次模型请求，未确认 usage=0、预留=0。没有更换模型。预留为依赖配置价格/供应商输出限制的保守估算，不宣称供应商金额硬限额。

第一次直接执行原既有 mean 修复业务输入，模型 6 次、工具 6 次，任务 succeeded；仅暂停本轮 API，采集失败不影响任务。51 个显式 schema_version 事件保留在 SQLite spool，77824 字节、rejected=0。解除暂停后用 `--flush-only` 重新启动 exporter，pending=0；任务结果、workspace 和预算账本字节不变，模型调用数不增加。服务端实际 ObservedRun completed/complete、events=51、序号无缺口、dropped/truncated=0，六份 usage 共 8124 tokens。第二次直接任务在线送达 41 条事件，同一来源/会话，独立 run ID，succeeded/complete。真实工具包括 read_file、write_file、run_python，不依赖测试/评分成功结论。

同项目另一来源真实直接启动原任务，但额度仅 ¥0.000001，调用前预留拒绝：供应商 calls=0、费用=0，真实 limited 终态及 8 事件完整保存，不制造模型/工具输出。它的一次 model_start 是 ModelClient.complete 的本地尝试，随后 model_end 报 budget_exhausted，绝不当作已发送供应商请求。

私有证据保存在忽略目录 `data/observation-trae-20261012/`，包含原始响应、源任务、预算、spool 前后、Docker 日志/状态、页面文本与截图，不提交凭据、日志、私有正文或运行数据。

## 权限与重传初步结果

40 个具名真实 API 请求全部符合预期：A read/manage 读取真实详情/列表/来源 200；B read/manage 读 A 详情 404、按 A 来源筛选列表为空；来源凭据读详情/列表/来源或创建来源 401；项目 read/manage 冒充来源写入 401；read 创建/撤销来源 403、跨项目撤销 404，manage 撤销本项目来源 200，撤销后来源 heartbeat/events 401。

来源 A 对自己的 external run heartbeat accepted=true，A2/B 对同一 external run accepted=false；不能通过 payload 指定 source_id，extra 字段 422。当前写入归属由来源令牌决定，来源内 external ID 命名空间不等于服务器 ObservedRun UUID；不把持有来源令牌者限制为单 run，也不擅改项目读取为来源读取。A 的 read 允许看到 A/A2 两来源真实任务。

原真实 run_start 原样重传 200，事件及 metrics 不增加；修改同 event_id 的内容返回 409 event_conflict，原事件全行内容不变。负向冲突只提交被拒绝的原事件变体，不持久化伪造任务事实。后续页面节点、正常退出/再启动及最终残留检查在本页收尾追加。
