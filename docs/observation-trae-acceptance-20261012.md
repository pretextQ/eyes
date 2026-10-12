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

原真实 run_start 原样重传 200，事件及 metrics 不增加；修改同 event_id 的内容返回 409 event_conflict，原事件全行内容不变。负向冲突只提交被拒绝的原事件变体，不持久化伪造任务事实。正常退出/再启动及页面节点收尾如下。


## 页面、重新启动与最终收尾

浏览器以本轮 A/read 连接真实项目。列表显示两个 completed（同 source/session，不同 ObservedRun/external run ID）及另一个来源的 limited。点击会话后只显示对应来源的两个 run。在线任务详情实际是 5 轮、4 工具、41 事件，首任务是 6 轮、6 工具、51 事件，与 API/本地执行边界逐项对应；共 100 事件、3 真实 ObservedRun。限额任务的一次模型尝试注明本地调用拒绝，不冒充供应商付费调用。

实际打开流程图 read_file 节点，显示 stats.py 参数和真实读取内容；模型输入节点显示 SYSTEM_PROMPT/用户消息/初始文件，不包含隐藏 reasoning_content。工具记录带对应序号、tool_call_id、实际开始/结束和耗时。首轮 exporter 使用 result/content 字段时，正文只可在原始记录查看；适配到既有 UI 的 output/text/request 后用第二次真实运行核对，不修改第一轮已存事件。浮层在画布中通过适应全部节点/平移后核对可见内容，不把点击隐藏在画布外的节点视为详情验证成功。页面文本、列表/流程/工具节点截图留在私有证据目录。

API/Web/PostgreSQL 正常停止均退出 0，再按 PG 就绪→API readiness→Web 顺序启动。三份 run 详情、来源列表和 run 列表的完整 JSON 前后相同；实际事件 ID/序号/正文/终态/metrics 未改变。再启动 `--flush-only`，完整 API JSON 仍相同，spool pending/rejected=0，预算账本、两次原任务结果及所有 workspace 文件字节不变。51 个离线原始 payload 与服务端 content 按 event_id 比较完全相同。只读数据库计数为 experiments/case_runs/attempts/work_items/score_runs/runners **全部 0**，observed_runs=3、observed_events=100，证明这条路径没有依赖主动评测。

最终仅停止本轮 API/Web/PG。直接任务、在线任务、两次纯补传、初始化和迁移容器均退出 0；真实预算拒绝 CLI 按失败任务语义退出 **1**，已记录 limited 终态、无待发送或活动模型调用，不冒充退出 0。新增十个容器均 exited、paused=false，无遗留工作子进程或本轮宿主机采集进程。开始时 100 个原容器按 ID/Image/Mounts/Status/Running/Paused/ExitCode 核对无变化，原服务不受故障注入。没有 down -v、删除现场、数据库、凭据或失败记录。

## 实现、检查和未覆盖边界

trae 实现/静态检查/真实运行分别记录在其 [OBSERVATION.md](https://github.com/pretextQ/trae-agent/blob/main/docs/OBSERVATION.md)：代码 `c80287a`（预算修正）、`3ab5856`（直接任务/exporter/埋点），均已推送 origin/main。使用既有 trae 镜像依赖和只读挂载当前 trae/Eyes 源码，运行源码摘要/镜像/环境在私有目录保存；不称重新无缓存构建或原生 Windows 接入验收。Eyes `9dbc763` 的实际修复只有详情来源两处文案；后端协议、权限、数据库与评分代码未改。Ruff/format、字节编译及对应前端 lint/format/生产构建通过；文档另核对 diff 和本地链接，不代替运行证据。

保留的操作问题：首次 formatter 检查提示 Observation.tsx 风格，格式化后通过；限额任务的 CLI 退出 1 被私有 command 包装器报告异常，它是实际 budget_exhausted 的预期失败任务，不再次运行以隐藏记录。首次工作区脚本替换找不到格式化后的子串，未执行后续编辑/付费调用，修正查找后继续。没有生成或修改仓库测试、用例、fixtures、mocks 或评分口径，也未安装新依赖。

已覆盖真实正向、来源/项目范围、API 暂停持久保留/恢复补传、原样去重/拒绝冲突、按需停止/重启及真实页面。仍未注入强杀 exporter、spool 满、慢盘/磁盘耗尽、供应商缺 usage、响应丢失后的所有网络组合或长期运行；永久 4xx rejected 保留有代码，未对本轮正常 exporter 造坏批次去宣称正向验证。exporter/来源故障或崩溃不代表 Agent/供应商停止。已知脱敏不能保证自由正文无秘密；本地工具按原可信代码假设运行，不新增安全沙箱承诺。观测正文自动保留清理、第二 Agent 主动评测接入/双 Agent 并发、其余 M2/M4 矩阵及真实版本改善/退化仍未验收。24 小时不是当前要求。

本轮文档与实现均在各自仓库检查后分别提交推送；最后文档提交/推送哈希以最终 Git 输出为准。私有证据不进入任一仓库提交。
