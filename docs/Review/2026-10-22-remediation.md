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
