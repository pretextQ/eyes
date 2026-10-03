import {
  ArrowRight,
  ArrowUpRight,
  FileCheck2,
  FlaskConical,
  GitCompareArrows,
  Layers3,
  ListTree,
  Plug,
  SlidersHorizontal,
  Target,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useConnection } from "../connection";

const steps = [
  {
    title: "接入目标 Agent",
    description: "选择 HTTP 或 Python 接入，声明版本与观测能力。",
    icon: Target,
    url: "/targets",
    label: "配置目标",
  },
  {
    title: "导入测试集",
    description: "上传 JSONL，固定每条用例的输入与预期。",
    icon: Layers3,
    url: "/datasets",
    label: "准备数据",
  },
  {
    title: "定义评分口径",
    description: "发布规则或 Python 评分器，声明所需证据。",
    icon: SlidersHorizontal,
    url: "/scorers",
    label: "配置评分",
  },
];

export function WorkspaceWelcome() {
  const { openConnection } = useConnection();
  return (
    <section className="workspace-welcome" aria-labelledby="welcome-title">
      <div className="welcome-connection">
        <div className="welcome-symbol">
          <FlaskConical size={25} strokeWidth={1.5} />
        </div>
        <div className="welcome-connection-copy">
          <span className="section-label">开始第一场实验</span>
          <h2 id="welcome-title">开始验证你的 Agent</h2>
          <p>在一个工作台管理测试、审阅执行证据，并比较每次迭代。</p>
        </div>
        <button className="button primary" onClick={openConnection}>
          <Plug size={16} />
          连接实验空间
          <ArrowRight size={16} />
        </button>
      </div>
      <div className="welcome-workspace">
        <section className="welcome-checklist" aria-labelledby="setup-title">
          <div className="welcome-section-heading">
            <div>
              <span className="section-label">开始配置</span>
              <h3 id="setup-title">准备你的实验</h3>
            </div>
            <span className="muted small-text">连接后配置</span>
          </div>
          <ol className="setup-list">
            {steps.map((step, index) => (
              <li key={step.url}>
                <Link to={step.url}>
                  <span className="setup-index">0{index + 1}</span>
                  <step.icon size={20} strokeWidth={1.5} />
                  <span className="setup-copy">
                    <strong>{step.title}</strong>
                    <small>{step.description}</small>
                  </span>
                  <span className="setup-action">
                    {step.label}
                    <ArrowUpRight size={15} />
                  </span>
                </Link>
              </li>
            ))}
          </ol>
          <div className="setup-next">
            <FlaskConical size={16} />
            <span>配置就绪后，创建实验并审阅每条用例的结果。</span>
          </div>
        </section>
        <aside className="welcome-review" aria-labelledby="review-title">
          <span className="section-label">证据审阅</span>
          <h3 id="review-title">每个结论，都能追溯</h3>
          <p>从一场实验，深入到一次执行。</p>
          <ol className="review-path">
            <li>
              <ListTree size={17} />
              <div>
                <strong>执行过程</strong>
                <small>按用例查看尝试、事件与产物</small>
              </div>
            </li>
            <li>
              <FileCheck2 size={17} />
              <div>
                <strong>评分依据</strong>
                <small>核对评分口径、结论与证据引用</small>
              </div>
            </li>
            <li>
              <GitCompareArrows size={17} />
              <div>
                <strong>迭代对比</strong>
                <small>并列审阅配置和逐用例结果</small>
              </div>
            </li>
          </ol>
          <Link className="text-button" to="/guide">
            了解接入与观测范围
            <ArrowRight size={15} />
          </Link>
        </aside>
      </div>
      <div className="welcome-footnote">
        <span className="status-dot" />
        <span>尚未连接 · 实验数据将在认证后加载</span>
        <Link to="/guide">
          接入指南
          <ArrowUpRight size={13} />
        </Link>
      </div>
    </section>
  );
}
