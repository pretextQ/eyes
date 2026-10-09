# Eyes Web 控制台

控制台位于 `frontend/`，使用 React、TypeScript、Vite、React Router、TanStack Query 和 Lucide 图标。基础组件采用 shadcn 的 Base UI 版本与 Tailwind CSS 4，配置位于 `components.json`。设计采用白色画布、浅灰侧栏、深色主操作、细边框和表格布局；颜色、字体、圆角与间距集中于 `src/styles.css`。字体通过 npm 依赖打包，不需要访问外部字体服务。

## 本地启动

需要 Node.js >=22.12 和 npm。首次安装使用锁文件：

```sh
cd frontend
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
| 回归报告 | `/comparison` | 创建与读取固定报告、评分配对与门槛、改善/退化/不可比原因及证据跳转；历史 ScoreRun 显式选择已实现，完整行为验收待完成 |
| 目标 Agent | `/targets` | 版本目录、固定配置详情、发布接入配置、隔离/恢复/观测能力和密钥引用 |
| 测试集 | `/datasets` | 文件或文本 JSONL 整体导入、服务端错误行详情、已发布用例检索 |
| 评分口径 | `/scorers` | 发布规则/Python 插件配置、实现摘要、证据要求、数值语义和超时 |
| 运行状态 | `/operations` | 后端就绪状态、队列分布、Runner 注册能力与最近心跳 |
| 接入指南 | `/guide` | 启动与接入流程、权限/观测边界、API 文档链接 |

管理操作由后端鉴权；只读令牌提交管理操作时展示 403。数据视图覆盖未连接、加载、空数据、查询错误和部分数据不可用状态。正在提交的按钮禁用，失败后保留表单内容及错误详情。

创建实验使用 `Idempotency-Key`；同一表单参数在失败重试时保留原键，参数变更产生新键。普通请求有 30 秒超时，产物下载为 60 秒。实验、用例、事件和运行状态每 10 秒轮询；后端就绪状态每 15 秒轮询。实验、用例、事件和清单采用每页 50 条；版本选择和对比会分批完整读取，避免将第一页误当完整数据。

清理、执行、证据和评分独立展示。取消操作标注停止确认边界。未知状态核对需填写依据并明确确认目标停止；重新评分创建新记录，原评分及固定清单保留。事件显示接收顺序、发生时间、生产者、序号与父 Span，不推断跨生产者的全局执行顺序。

执行审阅页在队列尚无 Attempt 时可先打开；轮询出现首个尝试后自动使用该尝试加载详情。若用户已选择仍存在的历史尝试，轮询保留该选择。

## 当前比较能力的边界

Web 通过 `POST /v1/comparisons` 创建固定报告，使用幂等键重试同参数请求；列表和详情直接读取服务端报告，不在浏览器重新计算改善、退化或门槛。`/comparison?new=1` 创建报告，`?baseline=...&candidate=...` 可预选实验，`?report=...` 可重开历史报告。生成后状态与选择保持不变，重新比较会创建新报告。

创建表单默认按相同摘要配对评分器，允许人工调整或跳过，每侧评分器只可使用一次，最多 20 组。可配置每组退化上限、可比覆盖率、候选通过率、执行成功率和数值容差。默认使用服务端的首个成功 Attempt 与最早评分；Web 暂不提供指定 ScoreRun 的创建选项，但能展示 API/CLI 创建的显式评分选择报告。

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

Compose 已增加 `frontend` 服务：

```sh
docker compose --env-file deploy/.env -f deploy/compose.yaml up --build -d
```

前端等待 API 健康后启动，本机访问 `http://127.0.0.1:8080/`。Runner 继续在目标环境独立运行。前端和 API 端口均限制在本机；部署说明与真实运行边界见 [后端说明](backend.md)。

## 本次验证记录（2026-10-02）

- 已通过 TypeScript 检查、ESLint（无报错或警告）、Prettier 和 Vite 生产构建。
- 已启动 Vite 开发服务与真实 Eyes API；通过前端 `/api` 代理读取存活检查（200）、未认证实验查询（401）、数据库就绪检查（503）；OpenAPI 可通过代理取得。
- Compose 配置解析通过，不代表容器构建或运行已验证。
- 本机 Docker daemon 未运行，PostgreSQL 无可用连接，不能验证真实项目认证、导入、发布、执行、评分、取消与恢复闭环。
- 浏览器工具拒绝访问本地预览，返回用户未允许该访问；未完成浏览器视觉、断点、键盘与交互验收。CSS 已设置桌面、平板、手机布局和 reduced-motion，但这属于实现证据。
- 未创建、修改或扩展测试文件、fixtures、mocks 或 snapshots；未执行真实 Agent 联调。仓库当前无可运行的既有前端测试。

前端代码实现与构建完成，不代表完整产品、真实集成或各阶段验收完成。后续需在可用的 PostgreSQL、项目令牌和浏览器条件下验证实际流程。

## 2026-10-02：浏览器预览补充验证

- 重新运行 `npm run lint`、`npm run format:check` 和 `npm run build`，全部通过；build 包含 TypeScript 检查。
- 启动 `npm run dev -- --port 5173 --strictPort` 与 `.venv/bin/eyes-server`，前端监听 `127.0.0.1:5173`，API 监听 `127.0.0.1:8000`。
- 本次 Chrome 已允许访问本地页面。逐页打开实验、目标 Agent、测试集、评分口径、结果对比、运行状态和接入指南，未连接状态正常显示；实验深链接刷新成功，浏览器未记录警告或错误。
- 检查桌面默认窗口、768×1024 平板和 390×844 手机布局；目标目录与实验工作台未见明显溢出，手机导航可展开并切换至目标页面。
- 连接弹窗可打开，空令牌时连接按钮禁用，Escape 可关闭弹窗。本次未提交项目令牌。
- 通过前端代理再次验证 `/api/health/live` 为 200、`/api/v1/experiments` 为 401、`/api/health/ready` 为 503（数据库不可用或未迁移）。
- 以上补充了页面显示和基础交互证据；连接后的加载、空数据与错误状态、业务表单、实验详情、执行证据与真实 Agent 流程仍未验收。未修改前端源码或测试。

## 2026-10-02：审查修复后的复查

- 修复用例对话框的 Attempt 选择：没有有效历史选择时从最新轮询结果取最新 Attempt，已有有效选择则保留。
- 本次修改后 `npm run lint`、`npm run build`（含 TypeScript）和 `npm run format:check` 全部通过；未新增或修改测试。
- Chrome 刷新实验工作台并打开/关闭连接弹窗，页面正常、空令牌按钮禁用，控制台无 warn/error。前端 `127.0.0.1:5173` 和更新后的 API `127.0.0.1:8000` 保持运行。
- PostgreSQL 就绪检查仍返回 503；因此首个 Attempt 随轮询出现的实际交互只完成源码核对与构建验证，未完成真实业务验收。后端修复记录见 [验证记录](backend-validation.md#2026-10-02代码审查的六项修复)。


## 2026-10-03：前端品质迭代

实验工作台现在根据连接状态组织首屏；执行审阅从弹窗移为独立页面；配置对比先显示可核对的条件，再进入逐用例记录。JSON 提供完整复制、长内容折叠和匹配行检索；导航保留列表筛选、用例分页和审阅标签。

本次通过本地独立 PostgreSQL 项目完成实际认证、配置发布、JSONL 导入、实验入队及配置对比的浏览器检查。未启动 Scheduler 或 Runner，全部实验保持排队状态。按用户要求继续暂缓真实 Agent 联调，因此有真实事件与评分的完整审阅验收仍未完成。

ESLint、Prettier 和生产构建（含 TypeScript）均通过。检查了手机、平板、桌面和宽屏布局，并在 Safari 补查认证、原生弹窗和长表单滚动。详细范围、修复循环、截图与未通过项目见 [前端质量记录](frontend-quality.md)。历史记录中的数据库不可用为此前状态，本次隔离项目就绪。

## 2026-10-03：组件模板参考与工作台优化

本轮参考 [21st 的 App Dashboard Layout](https://21st.dev/@shadcnstore/components/app-1)、[Sidebar 集合](https://21st.dev/community/components/s/sidebar)，以及 shadcn 的 [Sidebar](https://ui.shadcn.com/docs/components/base/sidebar)、[Command](https://ui.shadcn.com/docs/components/base/command)、[Empty](https://ui.shadcn.com/docs/components/base/empty)、[Skeleton](https://ui.shadcn.com/docs/components/base/skeleton) 和 [Table](https://ui.shadcn.com/docs/components/base/table) 的结构与交互。继续使用 Eyes 现有颜色、字体和基础组件；快速导航直接使用 `cmdk`，通过独立代码块按需加载。

- 侧栏分为实验与审阅、版本与配置、工作空间；桌面与平板可收起成图标栏，手机沿用抽屉导航。
- 顶部快速导航支持中文名称、英文别名和用途搜索；`⌘ K` / `Ctrl K` 打开，方向键选择，回车跳转，Escape 关闭。业务表单打开时不响应导航快捷键。
- 未连接首页改为连接入口、三步配置清单与证据审阅路径，不显示虚构实验或完成进度。
- 实验列表增加当前页结果数、清除筛选、创建时间排序、舒适/紧凑视图和同步反馈。排序仅针对服务端返回的当前页；`sort`、`density` 随筛选条件保存在 URL 中，从实验详情返回时恢复。
- 实验、版本目录、用例列表使用共用骨架屏；空状态按用途显示图标。弹窗支持指定初始焦点并恢复触发点；表格可聚焦并局部横向滚动。

### 本轮验证

`npm run lint`、`npm run format:check`、`npm run build`（含 TypeScript）以及 `git diff --check` 通过。未新增或修改测试文件、用例、fixtures、mocks 或自动化 snapshots。

浏览器以已有 Eyes UI Review 项目的只读令牌连接真实 API，读取原有两场排队实验，验证当前页排序、密度切换、筛选无结果与清除、详情返回条件，以及桌面侧栏收起。恢复了该项目已停止的独立 PostgreSQL 容器；当前运行的 API 报告迁移版本为 `0001_control_plane`，本轮没有迁移数据库、修改业务记录或启动 Runner/Scheduler。本次不能作为当前 `0002_platform` 部署验收或真实 Agent 执行验收。

实验列表检查 390、768、1024、1440px，页面无水平溢出；宽表格使用内部滚动。修复了表头无障碍文本脱离表格滚动容器造成的页面溢出。未连接首页检查手机和桌面；手机导航、快速导航初始焦点、英文搜索、无结果、Escape 恢复焦点与跳转已实际操作。Safari 补查原生对话框、搜索焦点和回车跳转。完整读屏、真实事件与评分数据、大数据性能及全部页面的所有状态仍未覆盖。

新增快速导航块 49.54 kB / gzip 17.02 kB，主 JS 315.88 kB / gzip 100.81 kB；这些是构建产物大小，不是首屏性能测量。

### 界面截图

- [未连接工作台](frontend-quality/components-welcome-desktop.jpg)
- [真实实验列表（桌面）](frontend-quality/components-list-desktop.jpg)
- [真实实验列表（手机）](frontend-quality/components-list-mobile.jpg)
- [快速导航](frontend-quality/components-navigation.jpg)

## 2026-10-03：纯白主题与版式调整

根据用户对米白底色的反馈，改为纯白主画布与表面、浅灰侧栏和边线、深色主要操作。参考 [Vercel Geist](https://vercel.com/geist/introduction) 的中性色与分隔层次，以及 [shadcn Dashboard](https://ui.shadcn.com/view/new-york-v4/dashboard-01) 的导航和表格排版；同时查阅 Linear 与 21st 的页面参考。保留 Eyes 现有字体、图标和组件结构。

- 清理表格、输入框、提示、空状态和弹窗中的暖色硬编码，统一使用颜色变量。
- 调整标题和说明文字字号；简化品牌与侧栏帮助区域，空状态图标去掉倾斜装饰。
- 未连接首页改成开放式连接入口、配置清单和证据说明，增加内容区之间的留白。
- 实验统计、列表筛选、表格行和表单保持统一的中性色层次，状态色继续表达成功、警告与失败。

验证：ESLint、Prettier、生产构建（含 TypeScript）与 `git diff --check` 通过。浏览器检查 390、768、1024、1440px 布局，没有页面级水平溢出；宽表保留内部滚动。实际查看已有实验列表、评分目录、目标目录及接入表单，检查手机导航和快速导航打开/关闭。未连接首页检查手机和桌面，浏览器无 warn/error。没有提交业务表单、修改测试或启动 Agent 执行；本轮验证范围为样式和相关基础交互。

- [纯白首页（桌面）](frontend-quality/white-welcome-desktop.jpg)
- [纯白首页（手机）](frontend-quality/white-welcome-mobile.jpg)
- [实验列表（桌面）](frontend-quality/white-list-desktop.jpg)
- [实验列表（手机）](frontend-quality/white-list-mobile.jpg)

## 2026-10-03：shadcn 审美升级第一批

正式接入 shadcn Base UI 的 `base-nova` 样式与 Tailwind CSS 4，保留 Eyes 的 DM Sans / IBM Plex Mono 字体、白色画布和业务状态色。新增组件通过官方 CLI 安装到 `src/components/ui/`，公共业务组件继续作为状态语义与现有页面的适配入口。旧样式置于独立 CSS layer，避免覆盖 shadcn 控件的尺寸与交互状态。

- 全局导航使用 Sidebar / Sheet / Breadcrumb，桌面支持收起，手机使用模态抽屉；接入指南只保留一个导航入口，移除装饰性页脚。
- 未连接首页使用 Empty，以“连接项目”为主操作，保留接入指南链接；移除重复流程分区和宣传文案。
- 实验页移除首屏统计卡片；筛选使用 ToggleGroup，搜索使用 InputGroup，排序和密度进入 DropdownMenu，数据行使用 Table 和 Badge。标准/紧凑行高为 56/40px；排序、搜索、密度与返回条件继续保存在 URL / 路由状态中。
- 首次实验空状态根据真实目录决定下一步配置入口；骨架屏、错误提示和无结果恢复操作使用公共组件。已有业务表单通过 Dialog 适配，表单内部尚未全部迁移。

ESLint、Prettier、独立 TypeScript 检查和生产构建通过。浏览器读取已有项目的两条排队实验，验证筛选恢复、当前页排序、密度、详情返回、导航和连接错误；检查 390、768、1024、1440px 布局及 390×700 长表单滚动。Safari 补查连接弹窗与快速导航。没有提交业务表单、修改测试或运行 Agent。本批不是全站迁移或完整业务验收；详细证据见 [前端质量记录](frontend-quality.md#shadcn-审美升级第一批)。


## 2026-10-08 回归报告接入验证

- 前端 ESLint、Prettier、TypeScript/Vite build，以及后端 Ruff 检查与格式检查通过；未新增或修改测试文件、用例、fixtures 或 mocks。
- 从停止状态的 Deta PostgreSQL 卷只读复制出独立验证卷，使用 API 8048、Web 5178。原卷与原有实验记录未修改。
- 基线为既有真实 Deta 实验 `0c84eb9f-86f5-490e-aab8-d624c0713462`。通过公开 API 在副本中创建关联实验，保持排队，不启动 Runner、不生成虚构执行或评分。
- Chrome 中完成评分器配对、无配对时禁用提交、生成报告、历史列表、筛选空结果、固定 Attempt/ScoreRun 跳转及键盘焦点检查。检查 375、768、1280 宽度；表格在容器内横向滚动，页面没有横向溢出。
- 排队候选生成报告 `ed004908-4547-4621-b1ab-9bacdda6ff49`，门槛为 inconclusive。取消副本中的排队候选后生成 `dbeaa584-3ac8-4e4a-ade3-a8cc89ac7086`，门槛为 fail（执行成功率不足）。原报告仍为 inconclusive，内容摘要保持不变。
- 新用例详情接口读取所属实验的记录返回 200，错配实验返回 404，无认证返回 401。页面跳转固定到基线真实评分 `8fa0a5c9-30ae-476c-9572-2c797a4ea63a`。
- 暂停本次独立 API 后，刷新列表显示错误与重试；恢复 API 后重试成功。导出按钮触发了 Chrome JSON 下载。
- 本轮验证的是报告/控制台链路，未运行新的 Agent 或模型任务，未验证真实改善/退化样本、生产容量、多 Runner 并发或故障恢复。截图保存在本机忽略目录 `data/regression-console-review/`。

### 同日复查

- 修复“重新比较当前结果”丢失自定义门槛与评分器配对的问题：从原报告读取配置后再展示表单，原报告读取失败时显示重试，不退回默认门槛。切换创建参数会重新初始化表单。
- 重新比较保留门槛和原实验的评分器配对，按默认首个成功执行及最早评分规则重新读取结果；表单明确说明不沿用显式指定的历史评分。
- 在独立验证副本中使用原有运行数据生成报告 `892095ca-1ac6-4da1-85c3-7aaaa01aa725`；Chrome 确认重新比较保留门槛 `2 / 80% / 85% / 90% / 0.25` 与评分器配对，375 / 768 / 1280 布局检查通过。
- 修复后 ESLint、Prettier、TypeScript/Vite build、新增后端接口涉及文件的 Ruff 检查与格式检查，以及 diff 空白检查通过。本次未新增或修改测试文件，未运行新的模型任务。
