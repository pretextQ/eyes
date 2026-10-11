# Runner 可靠性修复与验收

日期：2026-10-11（Asia/Shanghai）。范围为审查 #3、#5 的本地恢复缺口及 #6；不重新开发协议、自动核对或版本迁移。审查材料的 P0 定级不作为实现依据；这些入口缺陷按 Runner 交付与评分可靠性问题处理。

## 损坏载荷隔离与恢复身份

- assignment、result、核对 journal 与 outbox 按文件校验 JSON、契约及关联身份。恢复沿用 `read_stored_contract` / `explicit_versions` 的缺版本历史读取策略，只在内存投影，不改原文件或摘要；新领取仍沿用 ClaimedWork。
- 工作目录名称须匹配已校验 UUID；出站 outbox 校验 key/文件名、UUID、固定请求路径、所属 Runner 状态目录及结果与 journal 一致性，防止异常标识进入目录/请求路径。
- 损坏工作使用 `corrupt.json` 原地隔离，保留 assignment/result、capture、workspace；禁止该目录恢复、封存和回收。损坏 outbox 原字节与配对 content 转入 `outbox-corrupt/<随机 UUID>/`，记录原文件名、错误类型与可读取的归属。不会生成正常结果、ack 或停止确认，不调用额度释放。
- 健康文件继续扫描和发送。隔离内容不占发送容量；诊断未知归属时保守阻止 sealed 完成/封存，维护者必须核对原始材料后处理，不能仅删除隔离文件绕过证据缺口。已知归属只阻止对应工作的封存。没有自动删除隔离目录。
- 容量不足使用单独 `OutboxCapacityError`；临时读取/写入错误记录文件与 errno 并保留重试，不归类为等待容量；损坏载荷记录文件与异常类型，避免输出含秘密的载荷/校验异常正文。身份指纹文件损坏仍拒绝使用状态目录：不能在凭据归属不确定时补传。
- Runner status 增加损坏 journal/outbox 计数。相关 Ruff check、format、字节编译和 diff 空白检查通过；真实隔离副本故障验证在下文另记，不以静态检查替代。
- 复核核对 result 的 envelope 路径字段时，非字符串等结构损坏同样按文件隔离，不能从契约选择器逃逸成整个恢复循环异常。

## 验收边界

复查 `data/safety-acceptance-20261011/` 已有真实记录，逐项核对后补齐缺口；私有材料、凭据、日志和运行数据不提交。本轮不开展版本回归或备份恢复，不新增/修改仓库测试、用例、fixtures 或 mocks。

## 评分基础设施错误

- 评分输入和固定清单中的产物读取，对 408/425/429/5xx、传输错误和超时最多读取四次，间隔 0.5/1/2 秒；每次请求与退避都受原截止时间、当前有效租约、取消及 Runner 退出信号限制。身份/清单不匹配不重试；不重新领取业务、不重新执行 Agent、不调用 rescore、不自动改历史汇总。
- 认证、租约、最终 API/传输故障与本地读写/完整性失败记录 `error`。仅固定证据视图明确 unavailable/expired，或平台明确返回 410 evidence_expired/artifact_unavailable 时记录 `insufficient_evidence`；评分器自身的明确证据不足结果继续保留。
- 产物下载保留真实 API 错误码，不能将所有 HTTP 失败统一包装成 artifact_unavailable；冻结清单中的产物标识在写目录/请求前进行 UUID 解析。
- 相关 Ruff check/format、字节编译与 diff 空白检查通过；未用模拟 API、评分或 Agent 输出替代真实运行。
