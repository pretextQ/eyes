# 订单第二次评测 unknown：定位、协调入口与验证

调查跨2026-10-16～17，Asia/Shanghai。开始基线252c7b4，Eyes工作区干净。
这是独立于评分器修复的任务；保留[第二次评测原记录](coding-regression-order-real-r2-20261016.md)。

## 只读核查结论

已阅读AGENT、README、架构、原记录及最新提交，并核查实际冻结源码、原始归档和当前源码。
实际Agent加载的是原容器只读挂载的sources/trae-src，11文件摘要逐项吻合原映射；
当前外部仓库D:\woker\trae仍在e6e03825d63ad764b4f2535e6db5cd10dcce1a97，工作区干净，
model_client.py字节与冻结副本一致。冻结Eyes 78文件摘要也吻合。

只读SQLite连接核对停机副本，integrity_check=ok。平台停机前详情、协议task/snapshot、
两次恢复assignment及原键一致；公开文档只列本地业务标识，不公开原键或凭据：

- Attempt：4e5050a6-623d-4270-83c4-5ee0cd70115d。
- Agent run：4a0e0810-a7cb-40e2-b011-2e37a21476f2，revision 3。
- 模型序号8 / call_index 7，2026-10-16 23:16:12.688993～23:16:13.449372北京时间。
- 原生事件：8 request、7 response、1 model_http_error，11 tool.call / 11 tool.result。
- 7响应输入50305、输出9206 token；账本缓存38464，spent_rmb=0.03102228，
  pending_rmb=0.184524，unconfirmed_usage_calls=0。
- 停机后账本与停机前归档摘要一致。另用无网络、只读挂载容器读取原Agent卷，当前账本和
  协议SQLite与停机归档逐字节一致，integrity_check=ok、唯一run。没有启动原服务或写入原卷。
  计数字段0不证明费用确认，HTTP错误在record之前返回。
- 平台归档显示unknown且reserved=true，两次查询均snapshot_received/applied=false。
  本轮没有重启原PostgreSQL或发起新原键查询；平台状态依据最新持久归档，非本轮实时SQL。
- 原9个具名容器当前全部exited；没有启动历史Runner、Scheduler或maintenance。

第8次错误结果保留HTTP500及正文503/ServiceUnavailableError，但客户端只提取有限正文，
没有保存响应headers；ModelError没有request-id字段，model.error事件也只有call_index/code。
协议结果与45条协议原生事件（平台归档共49事件）中未找到供应商request-id。
原错误正文顶层只有error，内部字段为code/message/param/type，正文同样没有request-id。
不能由“未保存”断言“供应商未返回”；
也不能把本地Attempt/run或LLM tool_call_id当作供应商请求ID。

| 独立事实 | 已知 | 缺失/限制 |
| --- | --- | --- |
| 远端停止 | 本地回调结束、服务已停 | 供应商原请求完成/终止且不再执行的确认 |
| 业务结果 | 第8次请求失败进入本地错误路径，保存unknown结果 | 不能推出整体订单任务已知终态或质量结论 |
| 费用 | 7次usage本地结算；第8次预留未确认 | 第8次计费/零计费、最终usage、账单；前7次尚未供应商对账 |
| 工作区清理 | Agent工作区及Runner work/quarantine保留 | 未实际清理，不能由远端停止或结算替代清理事实 |

## 源码边界与缺口

1. Eyes runner/reconciliation.query_original只GET capabilities、runs/by-key；Agent服务by_key
   只SELECT协议SQLite，现存result在重启时保留。不存在供应商历史查询或未完成后台回调，
   重复原键查询无法产生缺失事实。本轮不继续轮询。
2. Eyes自动核对校验task/attempt/run、revision及查询令牌。有效unknown仍保留占额；
   只有可信终态及停止确认才应用。当前没有证据证明此处错误释放或遗漏已具备的停止事实。
3. 现有manage `POST /v1/attempts/{id}/resolve`接收Resolution(status/reason/
   stopped_confirmed/output)，仅支持四种已知业务终态，成功需output；追加ResolutionRecord，
   保留previous_result，清理状态不自动成功。它不能独立登记停止、计费或清理证据，不能
   结构化绑定供应商请求身份；已协调后重试返回409，不提供人工证据ID的幂等协议。
4. Agent app.state.resolve_run是集成方内部回调，非受权限约束的外部人工证据接口；
   finish覆盖当前unknown快照，没有独立人工证据审计，不应直接用于本个案绕过证据要求。
5. trae BudgetLedger只有reserve/record，预留是聚合金额，未绑定持久单请求ID。
   _post丢弃响应头/响应ID，HTTP错误不进入usage结算；没有外部账单导入和冲突处理。
6. trae http_service用“无未确认费用”推导model_stop_confirmed，把停止与计费耦合。
   保守维持unknown避免误放行，但无法表示“已确认停止、费用仍未确认”。缺口在外部仓库，
   不能在Eyes里清账补救；修改前须按用户要求确认。

官方文档核查仅访问公开文档：[Chat API](https://mimo.mi.com/docs/zh-CN/api/chat/openai-api)、
[错误码](https://mimo.mi.com/docs/zh-CN/api/guidance/error-codes)、
[计价](https://mimo.mi.com/docs/zh-CN/price/pay-as-you-go)。Chat文档定义响应id/usage，
错误码页仅解释500/503原因；这些页面没有给出错误请求已停止或零计费保证，也没有提供
此Chat请求按原ID查历史/补usage的接口。不推断所有账户功能均不存在，没有访问账户。

## 最小方案与专项批准

用户在本聊天明确批准“A和B，仅实现及隔离验证”。下列方案范围已获实施授权；
原历史个案的应用、占额释放和文件修改仍未授权。

### A：Eyes人工证据入口，新增公共请求契约，复用现有表

建议独立 `POST /v1/attempts/{id}/reconciliation-evidence`，保留旧resolve不变。
请求包含evidence_id(UUID)、expected_task_id、expected_run_id、原幂等键SHA-256、
来源类型/受控引用/证据SHA-256/事实时间，以及分开的stop/outcome/billing声明。
不接收原凭据或完整模型请求/响应；来源引用不能含凭据或任意可执行/远程下载地址。

manage权限、项目范围、原请求身份和来源字段全部校验；只保存脱敏证据引用与摘要。
同evidence_id同载荷返回同一回执；不同载荷、身份冲突或已应用终态矛盾返回409。
用既有调度锁和ResolutionRecord JSONB原子追加前后状态、操作者、来源及是否应用。
不新增数据库结构。默认仅登记事实，不改状态、不释放额度、不评分、不清理。
仅业务终态和停止证据同时齐备时才可显式请求复用resolve应用；费用缺失继续未确认，
费用证据本身不构成业务终态。停止已知而业务未知仍保留unknown和占额，避免改变状态语义。

该方案是公共API新增，批准后已实施。没有用reason塞入隐式协议。
实际请求契约为ReconciliationEvidence（`src/eyes/contracts/reconciliation.py`），
通过`/v1/contracts`及普通控制Schema导出；旧Resolution请求和外部Agent协议均不变。
API先升级，新入口缺失的旧API不可使用此功能；无需数据库迁移。
expected_attempt_id也必须匹配路径；source_reference是私有证据登记UUID，非自动下载URL。
来源枚举为supplier_record/operator_review，须附证据文件摘要与事实时间。
权限表示manage操作者对已经人工核实的事实作有责任的声明，服务器校验来源形状及身份，
不会仅凭摘要或来源字符串就宣称完成供应商真实性鉴定；原始证明须在受控私有档案保留。
重复同证据ID返回首次回执；同ID不同内容、同操作已登记的相矛盾业务/费用结论均409。
当前没有证据更正/退款演进协议，矛盾新事实需另行审查，不能覆盖前项。
显式应用succeeded沿用旧resolve的评分排队语义；本轮仅用failed合成材料验证，不生成评分。

### B：外部trae诊断与账本协调，需外部仓库修改授权

在D:\woker\trae增加请求前的持久本地call_id和绑定(run/attempt/call_index/
请求摘要/Key受控指纹/模型/起止时间/价率/预留)，不保存完整敏感载荷。
_post仅白名单提取响应ID、request-id类响应头及HTTP/error code，限制长度和字符，
通过错误事件和持久请求记录传播；不保存Authorization或任意响应头/正文。
供应商没返回ID时明确缺失；不追溯编造本次已丢失ID。

增加仅管理员本地离线结算命令，受私有文件权限及排他锁保护，校验原call身份、
来源凭据摘要、证据ID、重复与冲突，原子持久化前后金额和审计；无账单不结算。
停止证据与计费证据分别记录，终态必须独立确认。历史聚合pending只能经明确审核
绑定到本次唯一未确认请求后再结算，绝不自动迁移清零，也不按时间推断停止。
账本JSON格式须版本化、旧文件保守可读；未知旧pending继续阻止新付费调用。
不修改本轮冻结源码、原协议库或原预算文件；不顺带调用模型。

外部仓库及其文件兼容变化已获批准；具体实现结果在交付节追加。即便入口完成，处理原历史个案
仍需供应商证据及单独应用授权，本轮明确不释放占额或修改原文件。

## 一次性所需外部证据及后续使用

由用户在实际Key所属MiMo开放平台的请求明细/账单获取，若无明细，可由用户通过官方
支持渠道获取（本代理不访问账户、不发送消息）：

1. 将上述北京时间窗口、模型mimo-v2.6-flash、非流式POST /v1/chat/completions、
   max_completion_tokens=8192、HTTP500/正文503与Key受控标识关联的供应商请求ID；
   若无ID，须提供供应商能唯一定位原请求的证明，不能仅凭账户总余额。
2. 该请求完成/终止且不会继续执行的明确供应商记录，含事实时间和来源。
3. 原请求最终计费：输入/缓存/输出usage、实际扣费/价率/账单行；零计费必须明确确认；
   有退款须同时保留扣费和退款事实。前7次账单也需逐项或可唯一隔离的批次对账。
4. 证据导出文件保存在私有目录，保留来源、获取时间和字节SHA-256；不在仓库公开Key、
   敏感请求/响应或原始账单。身份相符后分别送入批准后的Eyes事实入口和trae结算入口。

定位时旧resolve只能在已知业务终态且确认停止时使用，并由manage人工核对身份及reason；
当时没有符合本轮要求的预算导入入口。批准后新增入口见下节，仍不能手改pending。
仅提供停止或费用中的一项不会
自动解决其他维度；即使代码修复完成也不能称原个案已解决。

## 本轮独立验证与交付

### Eyes任务A

新增`integrations/coding/verification/reconciliation.py`，仅合成ID/凭据/证据声明。
Windows PowerShell创建全新internal网络`eyes-unknown-verify-20261016`，新pg/state具名卷，
新PostgreSQL18.6容器（无宿主端口、无外网）。验证容器只有当前src/验证材料只读挂载及
新state卷；不挂载原历史环境、凭据或账本。测试通过ORM在空库创建当前模型表，不替代迁移验收。

实际命令参数（重复执行restart阶段前只重启本轮新PostgreSQL容器）：

```powershell
docker run --rm --init --user 0 --network eyes-unknown-verify-20261016 --read-only --tmpfs /tmp:rw,nosuid,nodev,size=64m --memory 1g --pids-limit 128 --mount 'type=bind,source=D:\projects\eyes\src,target=/app/src,readonly' --mount 'type=bind,source=D:\projects\eyes\integrations\coding,target=/work/integrations/coding,readonly' --mount type=volume,source=eyes-unknown-verify-20261016-state,target=/verify -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=/app/src:/work -e VERIFY_DATABASE_URL=postgresql+psycopg://postgres@verify-pg/eyes_unknown_verify -w /work --entrypoint /app/.venv/bin/python eyes-clean-control:20261011 -m integrations.coding.verification.reconciliation
```

初始阶段退出0、manual-evidence-api/passed=true。仅正常stop/start新pg容器，使用同命令
最后追加`restart`，新Python/API实例退出0、fresh-process-after-database-restart/passed=true。
使用httpx ASGITransport执行真实API/鉴权/事务，无网络模拟服务；没有启动业务Runner/Agent。

已实际覆盖：401/403/跨项目404；原attempt/task/run/key摘要不匹配409；非法来源/URL引用422；
未确认停止/未知结果申请应用422；证据不足、仅停止、仅费用保持unknown/reserved；
同证据同内容重复返回原回执且审计不增；同ID不同载荷及矛盾费用409；
明确停止及已知failed合成结果应用后reserved=false；前后事实及previous_result保留，
cleanup仍unknown、ScoreRun为0；数据库及API进程重启后同回执重复幂等，冲突仍拒绝。

`ruff check src migrations integrations/coding`、`ruff format --check src migrations integrations/coding`、
普通控制Schema导出和`git diff --check`通过。未运行前端、迁移或真实供应商验证。

提交`28124c0`已推送origin/main。

### trae任务B与最终收尾（2026-10-17）

外部仓库已完成请求身份/安全诊断、v2账本、分开的停止与费用事实，以及有权限、服务互斥、
身份/来源/重复/冲突校验和前后审计的离线入口。原价率/usage/实际金额不一致拒绝结算；
旧聚合pending必须先核对协议、账本摘要及唯一原请求，显式绑定后才能登记供应商证明。
绑定不改既有金额，不覆盖协议。已知供应商ID必须匹配；供应商明确确认无ID但能唯一
关联原请求时可显式登记该证明，不能由“本地没采到ID”推断。没有凭据/任意响应头/正文落盘。

trae提交`d58a814ffa5ee16342ebdf3ae392b9743a75b56a`已推送origin/main，
详细契约、命令、兼容及结果见[固定版本协调说明](https://github.com/pretextQ/trae-agent/blob/d58a814ffa5ee16342ebdf3ae392b9743a75b56a/docs/RECOVERY.md)。
BudgetLedger等旧导入路径保留，v1读取不迁移；首次新写入才写v2，未知未来版本拒绝。
v2不能直接降级旧二进制；服务/CLI需一起升级，未来冻结新提交/配置并发布新Agent目标版本。
本轮没有部署、发布或修改原冻结源码。

实际验证在本机无网络短命Linux容器，当前外部src及verification只读挂载，/tmp合成材料。
Python3.14.7/httpx0.28.1/Pydantic2.13.5，以MockTransport运行真实客户端解析和账本代码，
无供应商请求；六组场景均passed=true、驱动退出0。覆盖HTTP500/正文503诊断及敏感值
不落盘、身份/金额/来源冲突拒绝、证据不足、停止与费用分离、跨CLI进程重复幂等、
活动服务锁及文件权限、正常usage、缺usage、未知版本、旧pending显式绑定保留原金额、
协议字节不变，以及供应商明确无ID证明。其余环境/边界见外部记录，不冒称真实Agent复验。

trae `ruff check src scripts verification`通过，修改范围`ruff format --check src verification`
通过，`git diff --check`通过。扩大format到scripts时，未修改的submit_task.py两处既有格式
不通过，已如实记录，未为本轮改动该无关文件。初次身份反例使用非法哈希导致驱动未按
预期路径结束，修正合成材料后重验通过；没有掩去此失败。

本轮独立验证PostgreSQL已正常停止，新的验证卷保留；未启动任何历史普通Runner、
Scheduler或maintenance，原9个专用容器仍全部exited。原数据、五个卷、恢复材料、
原协议SQLite与预算文件均未修改；没有第三次订单执行、质量评分或模型调用。

**代码入口已完成，原个案仍未解决**：原unknown/执行占额保留；未确认预留¥0.184524保留，
前7次本地已结算¥0.03102228仍未供应商对账。平台状态依据最新停机归档，未重启原数据库
发起实时SQL。后续必须先取得上面的供应商证据，以新版入口在私有副本校验，再另获授权
应用到原环境；本轮批准不包含原历史应用。远端停止、业务结果、费用与清理仍分别协调。
