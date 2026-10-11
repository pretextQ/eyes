# Runner 可靠性修复与验收

日期：2026-10-11（Asia/Shanghai）。范围为审查 #3、#5 的本地恢复缺口及 #6；不重新开发协议、自动核对或版本迁移。审查材料的 P0 定级不作为实现依据；这些入口缺陷按 Runner 交付与评分可靠性问题处理。

## 损坏载荷隔离与恢复身份

- assignment、result、核对 journal 与 outbox 按文件校验 JSON、契约及关联身份。恢复沿用 `read_stored_contract` / `explicit_versions` 的缺版本历史读取策略，只在内存投影，不改原文件或摘要；新领取仍沿用 ClaimedWork。
- 工作目录名称须匹配已校验 UUID；出站 outbox 校验 key/文件名、UUID、固定请求路径、所属 Runner 状态目录及结果与 journal 一致性，防止异常标识进入目录/请求路径。
- 损坏工作使用 `corrupt.json` 原地隔离，保留 assignment/result、capture、workspace；禁止该目录恢复、封存和回收。损坏 outbox 原字节与配对 content 转入 `outbox-corrupt/<随机 UUID>/`，记录原文件名、错误类型与可读取的归属。不会生成正常结果、ack 或停止确认，不调用额度释放。
- 健康文件继续扫描和发送。隔离内容不占发送容量；诊断未知归属时保守阻止 sealed 完成/封存，维护者必须核对原始材料后处理，不能仅删除隔离文件绕过证据缺口。已知归属只阻止对应工作的封存。没有自动删除隔离目录。
- 容量不足使用单独 `OutboxCapacityError`；临时读取/写入错误记录文件与 errno 并保留重试，不归类为等待容量；损坏载荷记录文件与异常类型，避免输出含秘密的载荷/校验异常正文。身份指纹文件损坏仍拒绝使用状态目录：不能在凭据归属不确定时补传。
- Runner status 增加损坏 journal/outbox 计数。相关 Ruff check、format、字节编译和 diff 空白检查通过；真实隔离副本故障验证在下文另记，不以静态检查替代。

## 验收边界

复查 `data/safety-acceptance-20261011/` 已有真实记录，逐项核对后补齐缺口；私有材料、凭据、日志和运行数据不提交。本轮不开展版本回归或备份恢复，不新增/修改仓库测试、用例、fixtures 或 mocks。
