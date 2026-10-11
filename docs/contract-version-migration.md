# 公共契约显式版本与兼容迁移

2026-10-11（Asia/Shanghai）。普通控制契约现在要求显式 `schema_version: "1.0"`；统一 Agent 消息的 `protocol_version: "1.0"` 保持独立，不改外部 Agent Schema。数据库 head 仍为 `0005_reconciliation`，本任务无数据库迁移，不改已发布版本、实验摘要、证据清单、评分或报告。

## 核对出的入口

此前 Contract 的字段缺省为 1.0。它不仅影响顶层请求，也影响嵌套 Contract、Python 构造函数、JSONL 和持久化数据读取。依赖情况如下，不能把业务 Payload 中的任意同名字段当成契约版本：

| 入口 | 旧版实际情况 | 本次处理 |
| --- | --- | --- |
| 发布 TargetPublish/ScorerPublish | 顶层可缺省；capabilities、numeric 分别是 Contract；MewCode publish.py 未写顶层和 capabilities 版本，Deta 发布脚本已显式 | 更新 MewCode 生产端；Web 顶层与嵌套声明版本 |
| 创建实验、批次、比较及 resolve | Web 实验、批次/成员、resolve 未写版本；比较顶层已写，scorer_pairs/gate 未写 | 更新 Web 请求和类型；可选 gate 完全省略时由服务端创建带版本的默认策略 |
| CLI create/create-batch/compare | 直接校验输入文件；exclude_unset=True 曾将默认版本省略 | 文件现在必须显式；提供 migrate-schema 写新副本，仍保留其他默认字段的省略语义 |
| DatasetImport 与 JSONL | 导入包版本不能替代每行 CaseDefinition 的版本；缺省行曾被接受 | 默认每行严格，整体错误保留行号；原 Deta 三任务文件已显式，无需改用例 |
| Runner 注册/领取/lease/进度/结果 | 外层通常已写；python_agents 能力及执行/评分结果由默认构造后 model_dump 输出完整版本 | 更新全部本仓库生产构造；注册能力序列化形状不变 |
| SDK 事件、产物、封存及 observation | SDK 构造和插件构造依赖默认；网络封装通常已写；外部 Deta exporter 不在本仓库 | 更新 SDK 构造；批次和每个嵌套事件均严格；外部 exporter 需检查并升级 |
| Runner journal/outbox | 旧代码 model_dump 通常已显式包含版本；恢复读取也曾接受真正缺失的旧字段 | 仅持久化读取/传输投影允许带来源地补版本；新入队严格；保留原文件和非版本值 |
| 历史 Target/Scorer 快照 | 当前发布代码存储 model_dump，真实保留样本已显式；更早数据仍可能缺失嵌套版本 | 出站任务/评分/核对快照只做内存版本投影，不修改存储内容或原摘要 |
| 通用 HTTP result/reconcile、Python reconcile/评分插件 | 完整 ExecutionResult/ScoreOutput 曾可缺省；普通业务 output 字典不是 Contract | 完整契约输出严格；业务 input/output、config、SDK data 不补字段 |
| 统一 agent_http | AgentTask/Run/Result/Capabilities 的 protocol_version 原本必填；内部 TargetCapabilities/ExecutionResult 仍曾缺省 schema_version | 外部协议保持严格；更新内部映射构造与发现发布产物 |
| 重启自动核对（abd7e7c） | ReconciliationAssignment 顶层 API 响应未写版本，Runner 默认解析后 journal 已写；Submission 外层已写，snapshot 是 AgentRun | API 明确输出 schema_version；snapshot 仍按 protocol_version 校验，兼容窗口不能补它 |

普通 Contract 的子类包括 TargetCapabilities、ScoreSemantics、ScorerPair、GatePolicy、EvidenceView、ObservationEvent 等。因此只补顶层不足以通过校验。取消实验、rescore、retry 等无契约 body 的操作、二进制上传、健康接口和私有 Runner 控制消息不新增虚构的版本字段。

## 默认严格与有限过渡

默认不兼容缺失版本。只有管理员设置 **EYES_LEGACY_SCHEMA_UNTIL**，且请求明确带 **X-Eyes-Legacy-Schema: 1.0**，才允许为缺失的普通 Contract 字段按旧语义解释为 1.0。必须是带时区的绝对时间，配置上限固定为 **2026-11-01T00:00:00Z（北京时间 2026-11-01 08:00）**，可提前关闭，不能延长到上限之后。未设置、已到截止时间或头值不正确时拒绝兼容请求；即使原请求本身已经写版本，也应移除过期兼容头。

兼容响应（含校验失败响应）带 `X-Eyes-Schema-Compatibility: legacy-1.0`、`X-Eyes-Schema-Defaulted`（本请求补版本次数）、`X-Eyes-Schema-Sunset` 和 `Deprecation: true`。服务日志保留路由与次数，不记录请求体、鉴权头或秘密。必须借这些标记定位剩余旧客户端，不得长期静默补版本。窗口只补缺失 schema_version；显式不支持版本、未知字段和 protocol_version 都不会被改写。

例如仅在迁移期间把 API 环境设置为：

```dotenv
EYES_LEGACY_SCHEMA_UNTIL=2026-10-25T00:00:00Z
```

Compose 需通过 API 的 environment override 显式传入此变量，不能只放进未被 Compose 传入容器的宿主 `.env`。旧客户端必须自行加兼容头，或由维护者针对已识别旧客户端配置转发层；不按缺失字段自动识别所有请求。新客户端不使用兼容头。

## 升级顺序与支持边界

1. 备份数据库、证据卷和私有 Runner 状态，记录当前源码版本、插件摘要和 pending/rejected 数量。暂停新的实验及领取，先保存正在执行的结果；版本迁移不能绕过租约失效或 unknown 额度规则。
2. 先更新请求生产端：本仓库 Web、CLI、SDK、Runner、发布脚本、桥接和评分器已写版本，显式字段也可由旧 API 接收。外部脚本/observation exporter/完整 HTTP 结果生产者需同步升级。用户保存的请求与 JSONL 用以下工具迁移，不能直接编辑已发布数据。
3. 更新 API/Scheduler 至同一源码版本。默认严格；确需短期支持未完成迁移的调用方时显式配置窗口和请求头。兼容 JSONL 与嵌套声明都保留原规范化语义。
4. 更新 Runner 安装包及独立插件环境，再恢复领取。保留旧 state_dir 和原令牌/outbox；新 Runner 按原投递身份补传，不能签发新租约或创建业务执行来“迁移”未知任务。
5. 观察兼容标记与日志，完成旧客户端升级、排查 rejected 后删除窗口配置及旧头。截止时间自动结束公共入口补版本，最终只接受显式版本。

准备生产端更新不等于提前启用新版 Runner：API 包必须先于新版 Runner 恢复运行。特别是 abd7e7c 的核对领取响应顶层曾缺少 schema_version，新版严格 Runner 不能依赖其缺省解析；本次 API 已补显式字段。Web/CLI 的显式请求可先部署给旧 API，Runner 应按步骤 4 在控制端升级之后恢复。

旧客户端如果本来发出的完整线载荷已经包含所有版本，仍可使用原 API 形状；只凭客户端年代不能判断兼容。不带版本也不加兼容头的旧客户端默认不支持。窗口结束后，新请求必须升级；旧 outbox 则由升级后的 Runner 做持久化传输投影，不依赖公共 API 窗口。未经实际验证的外部旧二进制不承诺全面可用。

本任务修改了桥接/评分器构造源码，因此其源码摘要会变化。**不得重写历史 ScorerVersion/implementation_digest**；需要使用新源码时重新执行 plugins 获取摘要并发布新版本。尚需原评分器的旧工作应保留对应冻结插件/运行环境，或显式记录评分错误；不能用新代码冒充旧摘要。后续已验证新 Supervisor 配独立旧 Worker/SDK/冻结评分器，以及旧 Runner 完整组合，各 3/3、12/12，见[兼容验收](contract-compatibility-validation.md)；旧插件直接加载新严格 SDK、外部 exporter 和其他组合仍未验证。

## 请求文件与 JSONL 的显式迁移

```sh
uv run eyes migrate-schema --kind target --file old-target.json --output target-v1.json
uv run eyes migrate-schema --kind create --file old-create.json --output create-v1.json
uv run eyes migrate-schema --kind dataset --file old-cases.jsonl --output cases-v1.jsonl
```

kind 支持 target、scorer、create、create-batch、compare、dataset。工具无需 API 令牌，只对指定契约及其类型化嵌套边界添加缺失版本，保留所有非版本值及其他可选字段的省略；不扫描或修改业务 Payload。目标文件必须不存在，不覆盖原文件，所有行校验成功才写出。缺失字段、显式未知版本或未知字段仍失败，CLI 返回现有配置错误退出码 3，不输出原输入或凭据。迁移日志显示源类别和补版本的模型名。

最小 JSONL 行为：

```json
{"schema_version":"1.0","case_id":"answer-001","input":{"message":"说明该项目的用途"}}
```

这只是协议结构示例，不是新增评测用例。旧用例文件或冻结数据集不就地改写；迁移副本重新导入，或者在短期窗口内按旧语义发布。

## 幂等、旧 outbox 和历史读取

旧 Contract 的 model_dump 本来会输出默认的 schema_version=1.0。现在把它写入请求，不改变服务端规范化后的 digest。实验旧快照缺少 evidence_wait_seconds 时的原幂等回退规则保留；CLI/migrate-schema 不补其他默认字段，避免把旧请求的“省略”误变成新明确设置。批次及报告仍保留原模型字段与默认值，同键不同业务参数仍冲突。

read_stored_contract/explicit_versions 是**已持久化材料的读取/迁移边界**，不是公共请求的永久兼容模式。只在内存复制缺失的普通版本；对不支持版本和未知字段仍严格。日志标明 `legacy_stored_contract` 与 source，已发布 JSON、摘要、ScoreRun/Score 和原 journal 都不重写。这种历史读取可在公共窗口结束后继续，历史不会变成新请求的默认协议。

旧 outbox 在发送前按已有 kind/path 对应的公共契约验证并做内存投影，只补契约版本，不修改其他默认值、业务字段、事件 ID、产物 ID、Attempt、幂等键或 lease token。原 pending 文件在确认前保留，永久拒绝仍进入 rejected。旧已确认完成摘要按同一结果 model_dump 校验；迟到旧 lease 仍拒绝。无法解析的历史载荷保存为 invalid_stored_contract，不能伪造版本/结果继续发送。新入队载荷必须显式，不允许借历史读取绕过生产端错误。

## 错误与 Schema

| 情况 | 普通 API / JSONL 行为 |
| --- | --- |
| schema_version 缺失 | 422 invalid_request，details 的字段类型为 missing；JSONL 为 422 invalid_dataset，带对应行号 |
| schema_version 为 null、其他字符串或其他类型 | 422，literal_error；不转换为 1.0 |
| 未知字段或误用 protocol_version | 422，extra_forbidden；不会替代 schema_version |
| 兼容头在窗口未开启、过期或值不正确时使用 | 422 legacy_schema_unavailable |
| 普通 Target 配置中的 Agent discovery 缺失 protocol_version | 422 agent_config；不受普通兼容窗口影响 |
| 外部 Agent 消息不合法 | 沿用 Agent 独立 HTTP 契约与错误映射，不用内部 schema_version 替代 |

普通 Schema 移除版本 default，required 中包含 schema_version，additionalProperties=false 不变。`GET /v1/contracts` 返回各个可独立读取的 model Schema；`/openapi.json` 描述 API 请求。静态目录 [control-contracts-v1.schema.json](control-contracts-v1.schema.json) 使用各类型 `#/$defs/...` 引用：

```sh
uv run python -m eyes.contracts.schema > docs/control-contracts-v1.schema.json
```

统一 Agent 的 [Schema](agent-protocol-v1.schema.json) 和导出命令不变；其 protocol_version 原本必填，本任务没有改写该模型或导出文件。

## 实际检查和验证边界

本任务使用既有检查命令，不新增仓库测试、用例、fixtures、mocks 或模拟 Agent。静态检查、导入/编译和 Web 构建单独记录；不得以它们代替旧客户端运行验证。

通过 `ruff check src migrations integrations`、`ruff format --check src migrations integrations`、`python -m compileall -q src migrations integrations` 及 API/Runner 模块导入；Web 的 `npm run lint`、`npm run format:check`、`npm run build` 均通过。静态控制 Schema 从当前模型实际导出，外部 Agent Schema 保持原文件。

真实本机兼容操作使用新的私有 PostgreSQL 15 实例（127.0.0.1:55439）、独立 API 端口（严格 18050、窗口 18049）、新项目/凭据和证据目录。材料取自前次真实 MewCode 发布记录及原 Deta 三任务 JSONL；版本缺失/不支持/错字段检查仅改变协议元数据，不生成模拟业务输出。没有启动 Scheduler/Runner 或真实 Agent 执行，创建的独立实验与批次在领取前通过 API 取消。没有写入旧数据库、旧任务或旧 Runner 状态。

实际响应：严格缺失/未显式选择兼容均 422；窗口关闭的兼容头 422；窗口内历史格式发布 201，返回补版本计数 2；逐行缺失 JSONL 默认 422（整体不发布），窗口内 201/计数 3；显式不支持版本及误用字段 422；缺失 Agent protocol_version 为 422 agent_config。实验旧格式创建与显式迁移后的同键重放均 201，ID 和 request_digest 相同；批次同键重放保持同 ID。公开 Schema 的 required 包含版本。CLI 实际迁移历史格式目标副本及原三任务文件完成，原文件保留。

另启动实际已过截止时间的独立 API（18051），兼容头返回 422/legacy_schema_unavailable；迁移工具生成的目标副本向严格 API 发布为 201。现有 CLI 对严格 API 同键重放退出 0，实际 UTF-8 三任务导入退出 0。初次 CLI 导入因 Windows 默认 GBK 解码抛 UnicodeDecodeError/退出 3，已把 CLI 和 Deta JSONL 生产读取明确设为 UTF-8 后重新导入成功。首次误用 `python -m eyes.server.admin` 未调用该文件的 CLI 入口，空凭据输出导致采集中止；改用已有 eyes-admin 命令完成真实 bootstrap。初次 Web 类型检查暴露新增版本字段后的默认 gate/Draft 类型缺口，修正后完整 lint/format/build 通过。这些失败未作为成功运行证据。

另只读检查前次真实 Runner 保留的 6 份 completion journal（3 执行、3 评分）：它们原本已含版本，当前传输投影载荷和结果摘要全部保持相同。这是实际材料读取/摘要核对，**不是旧 outbox 的真实网络补传/服务确认**。记录保存在未提交的私有 `data/contract-version-migration/`，只汇报状态、计数与摘要比较，不输出凭据。

限制与待验证：Docker Linux 引擎不可达；Windows API `/health/ready` 返回 503/artifact_store_unavailable，目录 fsync 的既有平台限制未在本任务修复。PostgreSQL 迁移和以上 API/幂等操作实际运行成功，但不能称为完整部署、证据上传、评分或 Runner 验收。已接受完成的网络重传、真正缺少版本的历史 outbox、旧 SDK/外部 exporter/插件二进制、多进程并发与 evidence_wait_seconds 缺省更早快照重放仍待 Linux/真实旧环境验证。M0/M2 不因本任务而宣称完整通过。

随后用户要求继续兼容验收并优先修复 Docker：2026-10-11 Docker 运行时残留套接字隔离后，Linux 引擎恢复；使用独立历史数据库/产物副本验证了 6 份已接受完成载荷的旧版 Outbox 真实中断/恢复（6 个 duplicate 确认），以及旧 Runner/SDK/评分器、新 Supervisor+旧 Worker/SDK/评分器两组实际评分，各 3/3、12/12 检查通过。原执行、清单、历史评分及 journal 保留。具体版本、命令与仍未覆盖的边界见[兼容验收补充](contract-compatibility-validation.md)。上述初次环境限制作为历史失败记录保留，已接受结果重传与这两种组合不再标为完全未验证；其他旧客户端和真正缺版本的持久化载荷仍待验证。
