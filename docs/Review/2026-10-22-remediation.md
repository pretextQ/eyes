# 2026-10-21 审查逐项修复

按用户要求，每个独立修复在检查后单独提交并推送。基线为 `11e93ba`，Windows / PowerShell；用户明确要求沿用现有检查，不新增测试。原始报告保持原文，本文件记录复核与处理结果。

## H1：密钥引用格式

目标和评分器的公共契约统一限制合法 `env:NAME`（完整引用最多 260 字符），发布前拒绝明文和非法变量名；Runner 复用相同格式校验，仍执行环境白名单及平台令牌隔离。重新导出控制契约并更新接入/历史版本处理说明。不修改历史快照或摘要。

检查：`uv run --no-sync ruff check src migrations`、`uv run --no-sync ruff format --check src migrations`、控制契约导出、`git diff --check`。Docker daemon 当前未启动，未执行 API/Runner 或 PostgreSQL 运行验证。
