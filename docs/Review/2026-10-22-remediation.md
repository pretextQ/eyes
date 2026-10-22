# 2026-10-21 审查逐项修复

按用户要求，每个独立修复在检查后单独提交并推送。基线为 `11e93ba`，Windows / PowerShell；用户明确要求沿用现有检查，不新增测试。原始报告保持原文，本文件记录复核与处理结果。

状态：源码处理已完成并逐项推送 origin/main。原报告 20 项中 19 项包含代码修复，M9 经复核保持既有正确语义；另处理 4 项架构/部署观察及 2 项复核补充，共 25 个独立变更提交，最后单独提交本汇总。下列静态/构建检查通过不代表真实并发、恢复或容量验收通过。

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

## M7：汇总与详情无界加载

实验汇总使用数据库分组/窗口查询，保持首个成功 Attempt、最早评分、N/A 和全部分母语义，不加载执行输出、评分理由或证据。用例详情在加载前按数据库统计检查 16 MiB JSON/记录预算，超限明确返回 413 detail_too_large；可用 include_history=false 获取基本执行，再分页读取事件/清单/新增的 scores 端点。默认响应形状和历史选择不变，不静默裁剪。

检查：ruff 规范/格式、Python 编译、`git diff --check`；未执行 PostgreSQL 汇总对照或大数据压测。

## 架构观察：集成目录 CI

既有 CI 的规范/格式检查加入 integrations，不增加测试、依赖或新的 job。23 个集成 Python 文件已通过相同检查。

检查：`ruff check src migrations integrations`、`ruff format --check src migrations integrations`、`git diff --check`。

## 架构观察：代理上传限制

nginx 请求上限从 8 MiB 对齐后端默认产物上限 32 MiB；控制 API 的独立 JSON 8 MiB 限制继续生效。自定义更大产物上限时仍需同步修改代理配置。

检查：配置核对、`git diff --check`；未运行实际大文件上传。

## 架构观察：迁移 head 自动读取

readiness/备份恢复共用的 SCHEMA_REVISION 从实际 Alembic 单一 head 计算，移除手工常量。源码读取仓库迁移，wheel 打包迁移版本，Docker 在安装前复制迁移；无迁移或多 head 将明确失败。

检查：ruff、Python 编译、`alembic heads`、离线迁移 SQL 和 wheel 构建；未连接数据库执行迁移。

## 架构观察：公共工具的反向依赖

文件持久化/脱敏/密钥解析工具移到 eyes.common.files，后端观测、SDK、评分器和 Runner 从公共模块导入；HTTP 适配器直接使用公共契约的 origin 校验。保留 eyes.runner.files 兼容导出，旧接入不因模块移动断裂。新代码不再反向加载 Runner 配置或其包级运行环境。

检查：ruff（含 integrations）、Python 编译、CLI 帮助、wheel 构建；未运行真实接入。rules 等源码导入行改变会影响实现摘要，需保留旧冻结插件，使用新代码时重新获取摘要并发布新评分器版本；不重写历史摘要。

## L5 复核补充：代理别名

补齐 /api/docs、/api/redoc、/api/openapi.json 及 /redoc 的限制，避免通过通用 /api 转发重新访问文档。配置核对及 git diff --check 通过；未运行 nginx 请求验证。

## M9：复核后保持 unknown 语义

原报告将“明确 4xx”直接视为已知执行失败不符合现有公共边界。Runner 的 intended 仅在控制端 running 进度提交成功后置 true，启动前控制请求失败已经归 failed；执行派发后，通用 HTTP 目标的 4xx、Worker 异常或控制链路错误都不能证明远端没有副作用。只有未派发或进程范围执行得到停止确认时才可明确失败，其他情况保留 unknown/额度并核对。此项无业务代码修改，不将未知执行自动改成失败或重新执行。

## 其他复核结论

- H3 引用的事件/清单列表原本已有分页，修复针对累计量、封存及评分正文加载。
- M2 的同步 collect 当前均在一个事件循环执行，未找到并发重入证据；修复实际存在的后台异常静默退出。
- M6 的可信 Python 评分器是可扩展本地别名，允许先发布、后注册匹配 Runner；不以“暂时无人可领”判为非法。
- `6929b6d` 是 2026-10-14 交付基线，不是每次维护后的实时 HEAD，保留其历史含义。
- 原报告第四节声称 build 通过、第七节声称未运行 build，无法据此确定原执行事实。本轮已重新运行并明确记录构建结果。
- data 内私有材料已由 gitignore/dockerignore 排除，不读取或提交其中的凭据；既有 `.agent-teams/` 未跟踪目录保持原状。
- 用户明确不新增测试，本轮没有增加测试资产或 test job。

## 本轮整体验证

| 检查 | 实际结果 |
| --- | --- |
| `uv run --no-sync ruff check src migrations integrations` | 通过 |
| `uv run --no-sync ruff format --check src migrations integrations` | 113 文件通过 |
| `uv run --no-sync python -m compileall -q src migrations integrations` | 通过 |
| `python -m eyes.contracts.schema` | 导出成功，与更新后的受控文件一致 |
| `uv run --no-sync eyes --help` | 通过，包含明文连接显式选项 |
| `uv run --no-sync alembic heads` | `0007_cancellation_audit (head)` |
| `uv run --no-sync alembic upgrade head --sql` | 0001～0007 离线生成成功；仅指定无密码的离线占位 URL，未连接数据库 |
| `uv build --wheel --out-dir data/review-20261022-dist` | 通过，归档包含全部迁移版本 |
| `uv lock --check --default-index https://pypi.org/simple` | 31 包通过，锁文件无变更；本机镜像源差异未写入仓库 |
| `npm run lint` / `npm run format:check` | 通过 |
| `npm run build`（含 tsc） | 通过，2476 modules，Vite 构建 16.13 秒 |
| `git diff --check` | 通过 |

构建 wheel 和离线 SQL 位于 gitignored data 路径。Docker daemon 未启动，因此本轮没有执行 PostgreSQL 迁移升降级、API/Runner/Agent 服务请求、nginx -t、浏览器下载/CSP、真实取消竞态、配额并发/保存点、备份恢复、磁盘故障、长期容量或性能压测。上述运行边界均保留为待复验，不沿用历史验收冒充本轮通过。

## 提交对应

| 问题 | 已推送提交 |
| --- | --- |
| H1 | `a44763d` |
| H4 | `a6dc9ef` |
| H2 | `ed7c3cb` |
| H3 | `6b4341d` |
| M4 | `316b26b` |
| M5 | `24f1294` |
| M2 | `ab6f4c9` |
| M6 | `dbf3a1b` |
| L1 | `634f056` |
| L2 | `4c1a140` |
| L3 | `ec9bf0b` |
| L4 | `cd2e0d8` |
| L5 | `b161c97`，代理别名补充 `daf5018` |
| L6 | `3badc98` |
| M8 | `01d21c2` |
| M3 | `091f90f` |
| M10 | `d785f9d` |
| M1 | `86bef9a` |
| M7 | `b824d31`，显式 SQL 连接补充 `3000a79` |
| integrations CI | `755922f` |
| nginx 产物上限 | `73e0cdf` |
| 自动迁移 head | `90b50aa` |
| 公共工具分层 | `b5f2a46` |

升级前核对必填数据库地址、非回环明文控制连接的显式配置、事件/详情限额和本地保留期。修改评分器源码会改变实现摘要，保持旧环境处理旧冻结任务，使用新源码时重新发布评分器版本；既有评分、版本和摘要没有改写。
