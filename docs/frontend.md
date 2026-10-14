# Eyes Web 控制台

控制台位于 `frontend/`，使用 React、TypeScript、Vite、React Router、TanStack Query 和 Lucide 图标。基础组件采用 shadcn 的 Base UI 版本与 Tailwind CSS 4，配置位于 `components.json`。设计采用白色画布、浅灰侧栏、深色主操作、细边框和表格布局；颜色、字体、圆角与间距集中于 `src/styles.css`。字体通过 npm 依赖打包，不需要访问外部字体服务。

## 本地启动

当前开发宿主机为 Windows，使用 PowerShell。需要 Node.js >=22.12 和 npm。首次安装使用锁文件：

```powershell
Set-Location frontend
npm ci
npm run dev
```

打开 `http://127.0.0.1:5173/`。界面未连接时展示连接引导，不加载演示数据。

启动控制后端、迁移与调度进程的方法见 [后端说明](backend.md)。控制台在“连接设置”使用 read 或 manage 项目令牌进行认证，项目范围由后端令牌决定。令牌只保留在页面内存，关闭、刷新页面后需重新连接；不写入 localStorage、sessionStorage 或 URL。断开或切换项目会清除查询缓存。

开发与本地生产预览通过 Vite 将 `/api` 转发到 `http://127.0.0.1:8000`。后端地址不同时复制 `frontend/.env.example` 为 `frontend/.env.local`，配置 `EYES_API_PROXY_TARGET` 并重启开发服务。浏览器始终使用同源路径，前端不需要后端 CORS 变更。API 文档使用的 `/docs`、`/openapi.json` 和 `/v1` 也由代理转发。

## 页面与操作

| 页面 | 路由 | 当前实现 |
| --- | --- | --- |
| 被动观测 | `/observe`、`/observe/:id` | 来源/任务查询、事件流程图与节点详情；首页 `/` 跳转到 `/observe` |
| 多 Agent 批次 | `/batches`、`/batches/:id` | 创建、分页列表、成员独立配置与进度、整批取消 |
| 实验工作台 | `/experiments` | 服务端分页、当前页搜索与状态筛选、当前页排序、列表密度、创建实验 |
| 实验详情 | `/experiments/:id` | 执行汇总、明确分母的评分汇总、固定快照、分页用例、关联重跑、取消请求 |
| 执行审阅 | `/experiments/:id/cases/:runId` | 独立审阅页、本页用例导航、历史尝试、事件列表与详情、输入/输出、评分引用定位、证据清单和产物下载 |
| 回归报告 | `/comparison` | 创建与读取固定报告、评分配对与门槛、改善/退化/不可比原因及证据跳转；历史 ScoreRun 显式选择行为通过，真实版本改善/退化仍缺证据 |
| 目标 Agent | `/targets` | 版本目录、固定配置详情、发布接入配置、隔离/恢复/观测能力和密钥引用 |
| 测试集 | `/datasets` | 文件或文本 JSONL 整体导入、服务端错误行详情、已发布用例检索 |
| 评分口径 | `/scorers` | 发布规则/Python 插件配置、实现摘要、证据要求、数值语义和超时 |
| 运行状态 | `/operations` | 后端就绪状态、队列分布、Runner 注册能力与最近心跳 |
| 接入指南 | `/guide` | 启动与接入流程、权限/观测边界、API 文档链接 |

管理操作由后端鉴权；只读令牌提交管理操作时展示 403。数据视图覆盖未连接、加载、空数据、查询错误和部分数据不可用状态。正在提交的按钮禁用，失败后保留表单内容及错误详情。

创建实验使用 `Idempotency-Key`；同一表单参数在失败重试时保留原键，参数变更产生新键。普通请求有 30 秒超时，产物下载为 60 秒。实验、用例、事件和运行状态每 10 秒轮询；后端就绪状态每 15 秒轮询。实验、用例、事件和清单采用每页 50 条；版本选择和对比会分批完整读取，避免将第一页误当完整数据。

普通创建、关联重跑和批次创建失效实际比较选项查询 `comparison-experiment-options`。2026-10-11 已在真实 MewCode 隔离项目验证普通/批次创建后，无页面刷新即可在比较选项看到新实验，见[实际验收](deployment-regression-20261011.md#审查-4比较实验选项缓存)。

清理、执行、证据和评分独立展示。取消操作标注停止确认边界。未知状态核对需填写依据并明确确认目标停止；重新评分创建新记录，原评分及固定清单保留。事件显示接收顺序、发生时间、生产者、序号与父 Span，不推断跨生产者的全局执行顺序。

实验 completed 表示调度结束；取消用例仍显示 cancelled，结果汇总保留 cancelled_runs，不能从实验“已完成”推断执行或评分通过。2026-10-11 的真实排队取消和报告显示已核对；实验/批次详情及运行状态页提供分页取消审计，显示凭据操作者、服务端时间、理由与真实平台处理结果；批次可展开成员记录。规则与验证见[取消审计](cancellation-audit.md)。

执行审阅页在队列尚无 Attempt 时可先打开；轮询出现首个尝试后自动使用该尝试加载详情。若用户已选择仍存在的历史尝试，轮询保留该选择。

## 当前比较能力的边界

Web 通过 `POST /v1/comparisons` 创建固定报告，使用幂等键重试同参数请求；列表和详情直接读取服务端报告，不在浏览器重新计算改善、退化或门槛。`/comparison?new=1` 创建报告，`?baseline=...&candidate=...` 可预选实验，`?report=...` 可重开历史报告。生成后状态与选择保持不变，重新比较会创建新报告。

创建表单默认按相同摘要配对评分器，允许人工调整或跳过，每侧评分器只可使用一次，最多 20 组。可配置每组退化上限、可比覆盖率、候选通过率、执行成功率和数值容差。默认使用服务端的首个成功 Attempt 与最早评分；Web 已提供显式历史 ScoreRun 选择。上一轮 BUG-004 已验证表单选择，本轮在真实版本回归中再次核对默认/显式报告的固定评分与证据绑定，见[验收记录](deployment-regression-20261011.md#历史选择证据和-cli)。

详情按评分口径展示用例等权汇总、重复执行记录、门槛失败与证据缺口，并可导出完整 JSON。报告链接固定到其选中的 Attempt 和 ScoreRun；用例通过新增 `GET /v1/experiments/{experiment_id}/case-runs/{case_run_id}` 直接读取，不依赖列表分页位置。接口校验项目与实验归属。评分页可查看原评分的证据引用及清单，历史报告不承诺证据永不过期。

## 构建与部署

```sh
cd frontend
npm run lint
npm run typecheck
npm run format:check
npm run build
npm run preview
```

`preview` 用于本地审阅构建结果；正式部署使用 nginx。前端 Dockerfile 采用 Node 构建和 nginx 静态服务，`nginx.conf` 将 `/api` 转发给 Compose 的 `api:8000`，并支持 SPA 深链接刷新。静态资源有长期缓存，HTML 不缓存。

两个缓存 location 显式保留 server 已声明的 nosniff / same-origin 安全头。实际 nginx 1.30.5 上 HTML、assets 200/304、assets 404 和代理均已核对，见[部署验证](deployment-regression-20261011.md#审查-1nginx-安全头)。该记录是本机隔离 nginx 部署，不代表完整 Compose 发布验收。

Compose 已增加 `frontend` 服务：

```sh
docker compose --env-file deploy/.env -f deploy/compose.yaml up --build -d
```

前端等待 API 健康后启动，本机访问 `http://127.0.0.1:8080/`。Runner 继续在目标环境独立运行。前端和 API 端口均限制在本机；部署说明与真实运行边界见 [后端说明](backend.md)。
