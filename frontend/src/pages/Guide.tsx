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
        eyebrow="GETTING STARTED / 接入指南"
        title="从目标到证据"
        description="准备控制后端与 Runner，用一场真实实验建立完整记录。"
        action={
          <Link to="/experiments" className="button primary">
            前往实验
            <ArrowUpRight size={16} />
          </Link>
        }
      />
      <div className="guide-layout">
        <article className="guide-content">
          <section>
            <div className="guide-number">01</div>
            <div>
              <h2>
                <Terminal size={19} />
                启动控制后端
              </h2>
              <p>
                配置实际 PostgreSQL 连接，执行迁移并创建项目。API 默认监听
                127.0.0.1:8000，调度进程需要独立运行。
              </p>
              <pre>
                uv sync --frozen{"\n"}cp .env.example .env{"\n"}# 编辑
                EYES_DATABASE_URL 后执行{"\n"}uv run alembic upgrade head{"\n"}
                uv run eyes-admin bootstrap --name default{"\n"}uv run
                eyes-server{"\n"}# 另一个终端{"\n"}uv run eyes-scheduler
              </pre>
            </div>
          </section>
          <section>
            <div className="guide-number">02</div>
            <div>
              <h2>
                <KeyRound size={19} />
                连接项目并发布版本
              </h2>
              <p>
                在右上角“连接设置”输入 bootstrap
                输出的项目令牌。只读令牌可以查询；发布、创建实验、取消、状态核对和重新评分需要
                manage 权限。
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
            </div>
          </section>
          <section>
            <div className="guide-number">03</div>
            <div>
              <h2>
                <Plug size={19} />
                在目标环境运行 Runner
              </h2>
              <p>
                使用单独签发的 Runner 令牌，并在本机配置可信 Python 入口或允许的
                HTTP origin。评分器摘要从 plugins 命令读取。
              </p>
              <pre>
                cp deploy/runner.example.toml runner.toml{"\n"}uv run
                eyes-runner --config runner.toml plugins{"\n"}uv run eyes-runner
                --config runner.toml run
              </pre>
              <p>
                Runner 主动领取工作、续租、执行并上传证据。控制后端不替目标
                Agent 编排内部推理和工具调用。
              </p>
            </div>
          </section>
          <section>
            <div className="guide-number">04</div>
            <div>
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
            完整本地说明见项目 docs/backend.md 和 docs/agent-integration.md。
          </p>
        </aside>
      </div>
    </>
  );
}
