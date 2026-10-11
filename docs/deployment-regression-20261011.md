# 部署安全头与版本回归验收

日期：2026-10-11（Asia/Shanghai），开始基线 `261931d`。本轮遵循 [开发约定](../AGENT.md) 与 [计划](PLAN.md)，不重新实现前三个开发任务，不新增或修改测试、评测用例、fixtures、mocks 或模拟数据。私有原始响应、失败和运行材料保存于 Git 忽略的 `data/deployment-regression-20261011/`。

## 审查 #1：nginx 安全头

在两个声明缓存头的 location 内显式重复已有 `X-Content-Type-Options: nosniff` 和 `Referrer-Policy: same-origin`，避免 location 的 add_header 覆盖 server 级继承。没有增加 CSP、其他安全头或更改缓存、SPA 路由、API 代理。

本机 Docker Linux 实际拉取的 `nginx:stable-alpine` 为 **1.30.5**，镜像摘要 `sha256:0985e772fb9f729e6fa0980da05fca5d9c468e870eed43071545afa9d2e27d94`。采用显式声明方案也兼容未支持 header 合并指令的旧部署版本。`npm run build` 与容器内 `nginx -t` 通过。

独立容器 `eyes-deployment-web` 使用仓库 nginx 配置与真实前端构建产物，端口 18084；代理连接隔离安全验收 API 18056 / PostgreSQL 55443，未故障注入已有 MewCode 重验服务。通过实际 HTTP GET 记录 `headers.json`：

| 响应 | HTTP | 两项安全头 | 缓存 / 路由结果 |
| --- | --- | --- | --- |
| `/`、`/index.html`、SPA 深链 `/experiments/history/deep-link` | 200 | 均保留 | HTML、no-cache |
| 实际构建的 `/assets/index-*.js` | 200 | 均保留 | max-age=31536000、public、immutable |
| 不存在的 `/assets/missing.js` | 404 | 均保留 | 不回退 SPA，不附加成功缓存策略 |
| `/api/health/ready` | 200 | 均保留 | 实际 API ready、0005 |
| 未认证 `/v1/experiments` | 401 | 均保留 | 保持认证拒绝 |
| `/openapi.json`、`/docs` | 200 | 均保留 | 保持 API 文档代理 |

环境准备失败原样保留：首次 pg_ctl 输出路径不存在，随后正确路径启动成功；API 早于数据库启动而退出，导致 nginx 首次无法解析 api 上游。按依赖顺序重启后才进行上述 HTTP 验证。配置检查没有被用来代替 HTTP 结果。

## 验收状态

本节只确认 #1 的本机隔离部署结果；真实版本改善/退化与其余核对尚未在此记录完成，M3 不能宣称完整通过。
