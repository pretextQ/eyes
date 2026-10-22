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
