# 2026-10-21 审查逐项修复

按用户要求，每个独立修复在检查后单独提交并推送。基线为 `11e93ba`，Windows / PowerShell；用户明确要求沿用现有检查，不新增测试。原始报告保持原文，本文件记录复核与处理结果。

## H1：密钥引用格式

目标和评分器的公共契约统一限制合法 `env:NAME`（完整引用最多 260 字符），发布前拒绝明文和非法变量名；Runner 复用相同格式校验，仍执行环境白名单及平台令牌隔离。重新导出控制契约并更新接入/历史版本处理说明。不修改历史快照或摘要。

检查：`uv run --no-sync ruff check src migrations`、`uv run --no-sync ruff format --check src migrations`、控制契约导出、`git diff --check`。Docker daemon 当前未启动，未执行 API/Runner 或 PostgreSQL 运行验证。

## H4：接受后、启动前取消

取消入口在同一持久化写事务中将 accepted/queued 转成明确未启动的 cancelled；与 invoke 的 running 转换串行。invoke 遇到终态或 cancel_requested 不再调用 execute。已经进入 running 的后端继续使用真实取消回调和停止确认，不伪造终态。

检查：ruff 规范/格式、`python -m compileall -q src/eyes/agent_service`、`git diff --check`。未进行真实并发运行验证；后端启动/取消协调责任已在运行时文档明确。

## H2：控制面令牌传输

CLI、Runner 配置及 ControlClient 默认拒绝非回环 HTTP，发送令牌前校验。可信 Docker/私有网络通过显式 `--allow-insecure-http` / `allow_insecure_http` 选择；更新本机 Docker 示例及升级说明。没有按 DNS 解析结果自动信任远程域名。

检查：ruff 规范/格式、CLI `--help`、Python 编译、`git diff --check`；未验证实际 TLS/容器通信。

## H3：单 Attempt 事件与评分读取边界

普通摄入和未知执行的证据恢复均限制单 Attempt 10000 条/16 MiB 事件正文，去重后计额，既有 Attempt 行锁保护并发；拒收保留明确 413。封存改为只读取事件/产物 ID；超出新数量限制的历史轨迹生成明确 partial 的有界新清单。评分先在数据库聚合检查清单事件字节，再批量读取正文，保留原顺序。事件/清单列表原本已有分页，无需重复改造。

检查：ruff 规范/格式、Python 编译、`git diff --check`。未执行 PostgreSQL 并发/内存压测；16 MiB 为逻辑 JSON 正文限制，不代表数据库物理磁盘上限。

## M4：保存点重置配额基线

after_begin 的容量初始化仅在根事务运行；嵌套事务/SAVEPOINT 不再重新采样并覆盖根事务基线。取消批次的逐成员保存点保持原有回滚语义。

检查：ruff 规范/格式、`git diff --check`；未执行 PostgreSQL 保存点运行验证。

## M5：恢复产物发布顺序与持久化

恢复复制后逐文件和 staging 目录 fsync；先对 staging 与恢复后的数据库进行一致性审计，再准备 Runner 撤销/租约恢复，最后发布产物目录并 fsync 父目录。失败时保留 staging 并记录其路径，避免 pg_restore 已独立提交后丢失配套证据。恢复失败仍必须保持服务停止并人工核对。

检查：ruff 规范/格式、Python 编译、`git diff --check`；未执行真实备份恢复或断电验证。

## M2：后台证据泵异常

证据泵逐轮捕获并记录异常类型，继续重试；保留源文件和 outbox，不覆盖业务结果，转存失败数量可见。报告的 collect 并发竞态未获源码支持：当前 collect 为同步函数，调用均在同一个 asyncio 事件循环，没有内部 await 或线程调度；未添加无依据的锁。

检查：ruff 规范/格式、Python 编译、`git diff --check`；未执行磁盘故障注入。

## M6：不支持的目标与插件排队

发布时拒绝未实现的 adapter、缺失 Python Agent 别名、无效通用 HTTP 配置/URL/密钥映射及能力不匹配，避免永远不可领取的目标。可信 Python 评分器插件名仍是 Runner 的本地可扩展别名；允许在 Runner 注册前发布，因此缺少在线匹配 Runner 本身不是非法插件，也不自动失败或重跑。

检查：ruff 规范/格式、Python 编译、`git diff --check`；未运行实际发布/领取请求。

## L1：恰好 100000 条误报

达到 500 个满页后以 limit=1 探测下一条，仅存在第 100001 条才报超限；恰好 100000 条正常返回，持续满页异常仍有明确请求上限。

检查：前端 lint、格式、TypeScript 检查、`git diff --check`；未进行浏览器运行验证。

## L2：比较报告下载

下载链接先挂载 DOM 再触发，finally 移除；Blob URL 延迟 10 秒回收，与既有产物下载保持一致。

检查：相关文件 ESLint/Prettier、TypeScript 检查、`git diff --check`；未进行真实浏览器下载验证。

## L3：超时表单 setter 命名

目标/评分器和实验配置表单的本地 setter 改为 setTimeoutSeconds，避免遮蔽全局定时器，数值与提交语义不变。

检查：相关文件 ESLint/Prettier、TypeScript 检查、`git diff --check`。

## L4：框架 HTTP 错误 envelope

为 Starlette HTTPException 添加统一契约响应，404/405 具有 schema_version 和 error.code/message，保留 Allow 等原始响应头及状态码。

检查：ruff 规范/格式、Python 编译、`git diff --check`；未运行 API 请求验证。

## L5：Web 代理文档与 CSP

nginx 不再代理 /docs 和 /openapi.json；回环控制 API 的开发文档仍可直接访问。HTML、assets 和代理响应统一设置 CSP，仅允许本源脚本/连接，禁用对象和页面嵌入；保留 React/xyflow 所需的内联样式。

检查：配置逐段核对、`git diff --check`；Docker daemon 未启动，未运行 nginx -t 或浏览器 CSP 验证。

## L6：默认数据库凭据

移除 Settings 内置 eyes:eyes 数据库地址，要求显式 EYES_DATABASE_URL（环境或私有 .env）。Compose 已强制提供数据库密码；开发模板需自行更换示例密码。

检查：ruff 规范/格式、Python 编译、`git diff --check`；未连接数据库。

## M8：观测详情重复轮询

增加只读 summary 端点，观测页每 2 秒只轮询元数据；事件数量/过期状态变化或用户增加加载范围时才获取事件分页。晚到乱序事件同样增加事件数并触发重读；完成、心跳和失联状态由轻量元数据持续更新。错误可见，过期立即隐藏正文。

检查：ruff、相关文件 ESLint/Prettier、TypeScript、`git diff --check`；未验证浏览器网络请求或长轨迹性能。

## M3：本地已确认记录回收

Runner 已确认评分和恢复日志默认保留 7 天后回收，未确认/隔离/损坏/待发材料继续保留。Agent 参考服务按声明的终态保留期分批清理确定终态、事件、产物及超期无引用资源；活动/unknown 不清理。更新本地 SQLite 资源时间列，旧资源从升级起计时，明确幂等过期和物理文件边界。

检查：ruff 规范/格式、Python 编译、`git diff --check`；未执行 POSIX Runner 或 Agent 服务运行验证，没有删除当前 data 中的材料。

## M10：配额全表聚合

容量准入保留原有全局锁序，仅对写请求启用；before_flush 在首个事件变更前按受影响项目采样，根事务结束时只复核这些项目。无事件写入及普通读取不再聚合正文；容量状态只查询当前项目。主动事件通过已有 Attempt 项目/事件外键索引筛选，被动事件使用现有项目索引。不增加计量缓存、账本或迁移。

检查：ruff 规范/格式、Python 编译、`git diff --check`；未运行 PostgreSQL 并发、保存点或查询计划验证。

## M1：事件批次查询

按批次预取 producer/event 去重记录与原生事件 ID/序号冲突记录，在内存同步维护本批次新记录，最后统一 flush；避免每条事件都查询和写入往返。保持 producer 命名空间、Attempt 行锁和稳定锁序，不牺牲并发去重安全。

检查：ruff 规范/格式、Python 编译、`git diff --check`；未进行 PostgreSQL 批量摄入、冲突并发或吞吐验证。
