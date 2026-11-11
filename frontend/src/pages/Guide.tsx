import {
  ArrowUpRight,
  BookOpen,
  Code2,
  FileJson,
  KeyRound,
  Plug,
  Terminal,
} from "lucide-react";
import { Link } from "react-router-dom";
import { PageHeading } from "../components/ui";

export function GuidePage() {
  return (
    <>
      <PageHeading
        title="接入指南"
        description="启动 Eyes 后，可以接入日常观测，或运行带评分的批量实验。"
      />
      <div className="guide-layout">
        <article className="guide-content">
          <section>
            <h2>
              <Terminal size={19} />在 Windows 上启动 Eyes
            </h2>
            <p>
              使用 Docker Desktop 的 Linux 引擎。首次部署时在 Eyes 项目根目录的
              PowerShell 中复制示例配置。已有部署使用原配置。
            </p>
            <pre>Copy-Item deploy/.env.example deploy/.env</pre>
            <p>
              首次启动前，将 deploy/.env 的 POSTGRES_PASSWORD
              换成随机十六进制密码。 如果宿主机的 5432 已被占用，设置
              EYES_POSTGRES_PORT。
            </p>
            <pre>
              docker compose --env-file deploy/.env -f deploy/compose.yaml up
              --build -d --wait
            </pre>
            <p>仅在创建项目时运行 bootstrap。</p>
            <pre>
              docker compose --env-file deploy/.env -f deploy/compose.yaml exec
              api eyes-admin bootstrap --name default
            </pre>
            <p>
              在默认地址 http://127.0.0.1:8080
              打开控制台，通过“连接设置”输入项目令牌。
            </p>
          </section>
          <section>
            <h2>
              <Plug size={19} />
              日常观测
            </h2>
            <p>
              在“Agent 观测 → 接入 Agent → 远程 Agent 接入”用管理令牌创建来源。
              为支持事件上报的 Agent 配置可达的上报地址与生成的来源令牌，再在
              Agent 中发起任务。 只读项目令牌可查看记录。无需
              Runner、实验、测试集或评分器。
            </p>
            <div className="guide-links">
              <Link to="/observe">
                前往 Agent 观测
                <ArrowUpRight size={14} />
              </Link>
            </div>
          </section>
          <section>
            <h2>
              <KeyRound size={19} />
              批量评测 · 准备版本
            </h2>
            <p>
              使用管理令牌发布目标、导入测试集并配置评分器。发布 Python
              评分器前，先在已配置的 Runner 容器内执行下方的 plugins
              命令获取实现摘要。
            </p>
            <div className="guide-links">
              <Link to="/targets">
                目标接入
                <ArrowUpRight size={14} />
              </Link>
              <Link to="/datasets">
                JSONL 测试集
                <ArrowUpRight size={14} />
              </Link>
              <Link to="/scorers">
                评分口径
                <ArrowUpRight size={14} />
              </Link>
            </div>
            <p>
              目标的隔离、取消和幂等能力应按实际实现声明。发布后内容不可变，后续修改通过新版本进入新实验。
            </p>
          </section>
          <section>
            <h2>
              <Plug size={19} />
              批量评测 · 启动匹配的 Runner
            </h2>
            <p>
              根据 deploy/runner.example.toml 配置控制
              API、目标适配器、评分插件和私有状态目录。
              签发限项目、目标和工作类型的 Runner 令牌，通过 EYES_RUNNER_TOKEN
              提供。 Windows 上在已安装 Eyes 与所需插件的 Linux Runner
              容器内执行下列命令，配置路径以挂载为准。
            </p>
            <pre>{`eyes-runner --config runner.toml plugins
eyes-runner --config runner.toml run`}</pre>
            <p>
              Runner 主动领取工作、续租、执行并上传证据。控制后端不替目标 Agent
              编排内部推理和工具调用。
            </p>
          </section>
          <section>
            <h2>
              <FileJson size={19} />
              运行实验并审阅结果
            </h2>
            <p>
              选择目标、测试集和评分版本，设置并发、超时和重复次数。进入用例详情，分别核对输入输出、执行事件、评分记录与固定证据清单。
            </p>
            <p>
              使用“关联重跑”创建新实验；在“回归报告”选择基线、候选与评分口径，保存门槛结论并追溯执行证据。报告固定生成时的结果，与
              CLI 使用同一份记录。
            </p>
            <div className="guide-links">
              <Link to="/experiments">
                前往实验
                <ArrowUpRight size={14} />
              </Link>
            </div>
          </section>
        </article>
        <aside className="guide-aside">
          <BookOpen size={22} strokeWidth={1.4} />
          <h3>观测的边界</h3>
          <p>仅有任务接口时，只能证明输入、输出、错误与耗时。</p>
          <p>SDK 和目标轨迹覆盖实际埋点边界。没有采集到的内部步骤保持未知。</p>
          <div className="guide-divider" />
          <Code2 size={20} />
          <h3>开发者接口</h3>
          <p>交互文档和 OpenAPI 由控制 API 提供。</p>
          <a href="/api/docs" target="_blank" rel="noreferrer">
            API 文档
            <ArrowUpRight size={14} />
          </a>
          <a href="/api/openapi.json" target="_blank" rel="noreferrer">
            OpenAPI Schema
            <ArrowUpRight size={14} />
          </a>
          <p className="muted">
            完整说明见项目 docs/observation.md 和 docs/agent-integration.md。
          </p>
        </aside>
      </div>
    </>
  );
}
