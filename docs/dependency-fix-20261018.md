# 前端高危依赖修复计划与验证（2026-10-18）

基线：`a091e68`，Windows PowerShell / 本机 Docker Linux。用户授权先规划、依次实施、完成测试后提交推送。状态：修复与运行验证已完成，交付版本以本文件所属 Git 提交为准。

## 问题和方案

2026-10-18 Docker 构建和全量 `npm audit` 报告 7 个 high 依赖项：`shadcn`、`@shadcn/registry`、`ts-morph`、`@ts-morph/common`、`fast-glob`、`micromatch`、`braces`。根漏洞为 [GHSA-vfj7-8cjw-p6xm / CVE-2026-93687](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)：深度嵌套模式导致递归栈耗尽；查询时公告未列修复版本。7 项是同一漏洞在依赖链上的传播，不是 7 个独立漏洞。

项目仅在 `src/styles.css` 引用 `shadcn/tailwind.css`，没有执行 CLI 或引用其 JavaScript。选择保留现用 4.21.1 的完整 CSS 和 MIT 许可，移除未使用的 CLI 包及其传递依赖。保留现有组件、Base UI、设计配置与样式行为；不采用审计建议的 shadcn 1.0.0 降级，不使用忽略告警或覆盖漏洞元数据的方式。

## 顺序与验收条件

1. **保存样式与来源**：将已锁定 shadcn 4.21.1 的 `dist/tailwind.css` 原样复制至 `frontend/src/vendor/shadcn-tailwind.css`；MIT LICENSE 放在 `frontend/public/licenses/shadcn.txt`，随静态站点分发；记录来源和摘要；切换 CSS 引用。
2. **移除依赖链**：移除 `shadcn` devDependency，通过 npm 更新锁文件；保留其他现有包的版本。重新 `npm ci`，全量 `npm audit --json` 必须退出 0，核对七个包均不在锁文件和安装树中。
3. **同步维护说明**：说明项目组件在仓库内维护、vendor CSS 的来源和更新方法，避免重新引入未审计 CLI。
4. **修复后测试**：Docker Node 24 中执行干净安装、全量审计、lint、format:check、build；与修复前同一环境生成的 nginx 静态构建产物比较，若有差异先解释再交付。新 Compose 项目和新卷启动 PostgreSQL/API/Scheduler/nginx，运行既有 43 项 API 冒烟、真实 HTTP 页面/代理/鉴权检查、存储审计及正常停止重启检查。只使用既有测试驱动，不新增仓库测试套件，不调用付费模型。
5. **交付**：记录实际结果、失败与边界，检查 diff、许可、文档链接与 Git 状态，提交推送当前 main，并核对远端提交。

所有运行材料位于被 Git 忽略的 `data/dependency-fix-20261018/`，不提交凭据、数据库或原始业务数据。使用新的 Compose 项目和卷，不修改历史 unknown、费用账本或旧实验。

## 实施与验证结果

### 顺序实施

1. 已保存完整 637 行上游 CSS，SHA-256 为 `4c371f7a1ff5d219ae2f7ff28bd256b4346fd546fe46fbae22092e57db2f0fae`，与原安装文件逐字节一致。MIT 许可从同一包原样保留，摘要为 `1564074e13439397221ffd522e2e504d56561994a23d371aa5e3ad43e4f5423f`，通过 `/licenses/shadcn.txt` 随站点分发。vendor README 记录来源和更新流程。
2. 已执行 `npm uninstall --save-dev shadcn --ignore-scripts --no-audit --no-fund`，package.json 移除单个 devDependency，锁文件减少 262 个包条目；npm 对保留依赖做了去重/提升。逐项检查保留路径版本未改变，提升后的包也未引入基线之外的新版本。上述七个包在锁文件和 Docker 干净安装的 node_modules 中均不存在。
3. 已更新前端维护说明及文档导航，保留 `components.json` 和组件源码。`.prettierignore` 仅排除原样保存的上游 CSS，避免格式化破坏上游摘要；项目自有样式及 vendor README 仍正常检查。
4. 已按下表完成修复后测试；运行材料保存于 `data/dependency-fix-20261018/`。本轮服务均已正常停止，容器、镜像及新卷保留供复核。

### 修复后测试

环境：Docker Engine 29.8.2、`node:24-alpine`、Python 3.14.7、PostgreSQL 18.6；新 Compose 项目 `eyes-deps-20261018`，API/Web/PostgreSQL 分别只绑定本机 28118/28180/25439。

| 检查 | 实际结果 |
| --- | --- |
| Docker 干净安装 | frontend/Dockerfile 的 Node 构建阶段执行 `npm ci` 成功；使用锁文件，无宿主 node_modules |
| 全量依赖审计 | 容器中 `npm audit --json` 退出 0，info/low/moderate/high/critical 均为 0；并非仅审计生产依赖 |
| 七个告警包清除 | 锁文件检索、干净 node_modules 路径核对均无上述七个包 |
| 前端规范及格式 | 容器中 `npm run lint`、`npm run format:check` 均退出 0 |
| 类型与构建 | `npm run build`（`tsc -b && vite build`）成功；最终 nginx 镜像构建成功 |
| 静态产物对照 | 与同日修复前、同一锁定 Node 镜像生成的 nginx 产物比较，35 个原有文件的路径与 SHA-256 全部一致；最终唯一新增文件为 MIT 许可，共 36 文件 |
| 许可实际分发 | nginx `/licenses/shadcn.txt` HTTP 200，含原版权声明 |
| 数据库 | 新 PG18.6 卷上迁移 0001→0007，`alembic check` 无模型漂移；本轮没有再做降级，沿用同日修复前已通过的降级记录 |
| 控制 Compose | API/数据库 healthy，Scheduler 周期 sweep 正常，nginx 实际提供页面和代理 |
| 既有 API 冒烟 | 43/43 PASS，原 `data/fix-verification-20261017/smoke.py` 只读挂载；真实 PostgreSQL 与 `LocalArtifactStore`，`EYES_SMOKE_REAL_STORE=1` |
| 真实 HTTP | 14/14 PASS：HTML、JS、SPA 回退、代理 readiness、OpenAPI、401、认证列表、容量查询、目标/评分器发布、JSONL 导入、实验创建、取消、审计读取；另核对 nosniff 和 processed 审计内容 |
| 存储审计 | `eyes-ops audit` 为 ok，1 ready artifact / 2 manifests / 3 scores，problems=[] |
| 停止重启 | readiness 恢复；4 experiments / 2 attempts / 3 score_runs / 1 artifact 数量一致，产物 SHA-256 和存储审计前后相同 |
| 历史环境与收尾 | 原有容器状态及 StartedAt/FinishedAt 与本轮基线一致；本轮 5 个 Compose 容器均退出 0，未动历史 unknown 或费用记录 |

首次格式检查对上游 CSS 报格式差异，随后增加仅针对该 vendor 文件的豁免并重验通过；未把原失败记录改写为通过。既有 TestClient 输出 Starlette/httpx 弃用警告，不影响 43 项检查。

### 证据与复现入口

原始文件：`frontend-build.log`、`frontend-build-final.log`、`frontend-build-delivery.log`、`compose-build.log`、`frontend-nginx-final.log`、`npm-audit-final.json`、`smoke.log`、`http.log`、`assets-before.txt`、`assets-after.txt`、`assets-delivery.txt`、`audit-{before,after}.json`、`counts-{before,after}.txt`、`artifacts-{before,after}.json`、`service-logs.txt` 和 `baseline-containers.txt`。隔离数据库密码仅在私有 compose.env，不提交。

```powershell
docker build --target build -t eyes-frontend-check:deps-20261018 -f frontend/Dockerfile frontend
docker run --rm eyes-frontend-check:deps-20261018 npm audit --json
docker run --rm eyes-frontend-check:deps-20261018 npm run lint
docker run --rm eyes-frontend-check:deps-20261018 npm run format:check
```

完整服务通过 `deploy/compose.yaml` 配合私有 env 文件和 `-p eyes-deps-20261018` 运行，不使用默认项目或旧卷。冒烟入口沿用前轮驱动；不是新增的仓库测试套件或 CI。

### 边界

本轮通过移除未使用 CLI 消除项目依赖链，并未修改或修复上游 braces。零漏洞是本次审计数据库和锁文件下的结果，不保证未来没有新公告。未新增浏览器交互或视觉修改；用原有全部静态文件逐字节一致确认产物保持。API 冒烟的执行与评分结果由驱动提交，未运行真实业务 Runner/Agent、付费模型、负载或完整故障矩阵；不改变 M0～M4 原有验收结论。
