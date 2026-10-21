# Eyes 项目检查报告（只读）

- 检查对象：`D:\projects\eyes`，HEAD `b8ecab7`（2026-10-18），受版本控制文件 253 个
- 检查时间：2026-10-21 22:15 – 22:32（Asia/Shanghai）
- 执行方式：AgentTeams 团队 `eyes-project-audit`，3 名成员并行只读分析（架构 / 代码审查 / 测试），队长汇总
- 约束：全程只读，未修改任何项目源码、配置或数据；未启动 PostgreSQL / API / Runner，未执行真实运行验证
- 报告版本：v1（2026-10-21 22:32）

## 一、总体结论

| 维度 | 结论 |
| --- | --- |
| 架构边界 | 良好：`server` 独占 DB 与领域规则，客户端不依赖服务端 ORM |
| 技术栈一致性 | 良好：pyproject、Docker、CI、文档基本一致 |
| 静态质量 | 全绿：ruff、ESLint、Prettier、tsc 均通过 |
| 安全性 | 需关注：明文凭据引用、控制面明文 HTTP、取消竞态 |
| 资源健壮性 | 需关注：事件无总量上限、聚合接口无界加载 |
| 测试 | 零测试资产，CI 无 test job |

代码审查结果：**Blocker 0；High 4；Medium 10；Low 6**。无阻断级缺陷，但建议上线前优先处理 High 项的 H1/H2。

## 二、架构与技术栈

**分层**（Python 约 10.5k 行 / 79 文件，前端约 11.6k 行 / 54 文件）：

- `contracts/`（845 行）：公共契约层；
- `server/`（约 5,600 行）：独占 PostgreSQL、领域规则与调度；
- `runner/`（2,246 行）：仅通过认证 HTTP 领取/上报，不连库；
- `adapters/`、`sdk/`、`scorers/`：目标侧执行栈；`cli/`、`agent_service/` 只依赖 `contracts`。

**技术栈**：Python ≥3.14、FastAPI、Pydantic 2、SQLAlchemy 2.0（同步 Session）、Alembic（0001→0007）、psycopg3、PostgreSQL 18.6、OpenTelemetry SDK；前端 React 19.3 / Vite 8 / TS 6 / TanStack Query 5 / xyflow 12 / Tailwind 4 + nginx；Docker Compose 五服务部署。

**入口映射**：

| console script | 入口模块 |
| --- | --- |
| `eyes-server` | `eyes.server.main:main` |
| `eyes-scheduler` | `eyes.server.scheduling.worker:main` |
| `eyes-admin` | `eyes.server.admin:main` |
| `eyes-runner` | `eyes.runner.main:main` |
| `eyes` | `eyes.cli.main:main` |
| `eyes-ops` | `eyes.server.operations.main:main` |

前端：`index.html` → `main.tsx`（QueryProvider / BrowserRouter）→ `App.tsx` 路由；`/api/*` 由 Vite/nginx 去前缀转发到 FastAPI `/v1`。容器内 API 实际走 uvicorn factory，与 `eyes-server` 入口的监听地址/默认值不同。

**架构层关键观察**：

1. `runner.files` / `runner.config` 被 `server`、`adapters`、`sdk`、`scorers` 反向引用，存在分层泄漏与包级循环；
2. `/health/ready` 的 `SCHEMA_REVISION` 为手工常量，未与 Alembic head 自动校验；
3. 文档声明基线 `6929b6d` 与实际 HEAD `b8ecab7` 不符；
4. `data/` 577MB 含原生 PG 目录与 `pg-password.txt` / `credential.json`（已 gitignore，交付卫生仍需约束）；
5. nginx 8MB 与后端 32MB 产物上限不一致（当前未触发）；`integrations/`（2,365 行）未纳入 CI lint。

## 三、代码审查要点

### High（4）

| ID | 问题 | 位置 |
| --- | --- | --- |
| H1 | `secret_refs` 无格式校验，明文凭据可入库并由 read 令牌读回，违反"只存密钥引用"约定 | `src/eyes/server/catalog/service.py:49-65`、`src/eyes/contracts/target.py:42` |
| H2 | Runner/CLI 允许向非回环主机用明文 HTTP 发送 Bearer token（Agent 适配器则强制 HTTPS） | `src/eyes/runner/config.py:59-62`、`src/eyes/runner/client.py:24-32`、`src/eyes/cli/main.py:102-114` |
| H3 | 单 Attempt 事件无总量上限，`seal` / 评分输入 / 读取接口全量装入内存，可致 OOM | `src/eyes/server/evidence/service.py:69-108`、`src/eyes/server/evaluation/service.py:113-135`、`src/eyes/server/api/routes.py:484-513` |
| H4 | 取消到达后 `agent_service` 仍会调用 `execute`，产生副作用 | `src/eyes/agent_service/http.py:230-241` |

### Medium（10）

事件摄入逐 producer 加锁 + 逐事件查询（evidence/service.py:113-208）；Runner `collect()` 并发竞态且 pump 异常静默（runner/service.py:140-190）；Runner/Agent 本地 journal、恢复目录、workspace 无回收（runner/service.py:706-728）；`after_begin` 在 savepoint 重复触发重置配额基线（api/dependencies.py:17-39）；restore 先换 artifact root 后审计且未 fsync（operations/backup.py:174-214）；未知 adapter/plugin 永久 queued（catalog/service.py:49-97）；summary/case-runs 无界加载（experiments/service.py:122-224）；前端观测页每 2 秒全量重拉分页（Observation.tsx:454-475）；Runner 将明确 4xx 也归 unknown（runner/service.py:384-395）；配额检查每写请求全表扫描（operations/capacity.py:10-29）。

### Low（6）

分页在恰好 100000 条误报超限；比较报告下载 anchor 未入 DOM；`setTimeout` 遮蔽全局定时器；404/405 不走统一错误 envelope；nginx 暴露 `/docs` 且缺 CSP；`Settings` 内置默认凭据 `eyes:eyes`。

### 审查覆盖且未发现明显问题

认证/授权与项目隔离、路径/命令注入（无 `shell=True`、`eval`、动态 SQL）、前端 XSS 面与 token 存储、硬编码凭据。

## 四、测试与可运行验证

- **0 测试资产**：仓库无 `test_*` / `*.test.*` / `conftest.py` / vitest / jest 配置，90 个提交历史从未出现 test/spec 路径；后端 dev 依赖仅 ruff，venv 无 pytest；AGENT.md 明确禁止未经授权新增测试，属策略性选择。
- **实测通过**：`ruff check` / `ruff format --check`（`--no-cache`）；AST 解析 88 个 py 文件；`alembic upgrade head --sql`（620 行，head=0007）；CLI `--help`；前端 `lint` / `format:check` / `typecheck`（27s）/ `build`（26s，2476 modules）。仅产生 gitignored 产物。
- **CI 现状**：仅 backend lint、migrations（PG 18.6）、frontend lint/format/build 三个 job，无 test、无 coverage、未 lint `integrations/`。
- **覆盖缺口优先级**：
  - P0：`scorers/rules.py`（评分结论）、`runner/outbox.py` + `service.py` + `recovery.py`（投递/重试/恢复）、`scheduling/service.py` claim（686 行，SKIP LOCKED + 双配额 + 租约）、`evidence/service.py`（redact/seal/配额锁）；
  - P1：`api/routes.py` 60 路由、扫库恢复/核对/保留、`comparison` 与 `contracts`；
  - P2：adapters/sdk/agent_service、前端 `lib/*.ts`。
- **环境限制**：`runner.main` / `runner.worker` / `agent_service.http` 在 Windows 直接 ImportError（fcntl/resource）；代码含 PEP 758 语法锁定 3.14；本机 PG/Docker 不可用，无法复现迁移 CI。

## 五、共性风险（交叉验证）

1. **凭据与传输安全**（H1/H2 + L5/L6）：从"存储—传输—暴露面—默认值"形成完整风险链，应作为上线前第一优先。
2. **资源无界**（H3 + M7/M8/M10）：事件、汇总、轮询、配额扫描相互放大，大轨迹下最先出问题。
3. **取消与状态语义**（H4 + M9）：取消确认和 4xx 归类都会产生不可解释的 unknown。
4. **测试与可验证性缺失**（t3）：零测试 + CI 无 test job，使上述修复缺乏回归保障。
5. **生命周期与清理**（M3/M5）：长期运行会累积磁盘与半恢复状态。

## 六、建议行动顺序

| 优先级 | 动作 |
| --- | --- |
| P0 | 修复 H1/H2 凭据校验与 HTTPS 强制；为单 Attempt 设事件/字节上限并分页化读取；修复 H4 取消竞态 |
| P1 | 建立测试基建（dev 加 pytest + 首批无 DB 单测：scorers/contracts/evidence.redact/outbox），CI 增加 test job；修 M4/M5/M6/M10；`/health/ready` 自动校验 Alembic head |
| P2 | 前端分页/轮询优化、404 envelope、nginx 安全头与 `/docs` 关闭、默认凭据收紧、`integrations` 纳入 lint |

## 七、边界说明

- 全程只读：未启动 PostgreSQL/API/Runner，未执行真实运行验证，未运行 `npm run build`（会写 `dist/`）。
- 结论基于静态阅读与只读命令实测；运行时缺陷（并发、超时、真实故障注入）需后续测试验证。
- 详细原始报告保留在 AgentTeams 任务 t1/t2/t3 的 output 中；团队已归档。
