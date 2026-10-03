import { ArrowRight, Plug } from "lucide-react";
import { Link } from "react-router-dom";
import { useConnection } from "../connection";
import { Eye, SetupSteps } from "./ui";

export function WorkspaceWelcome() {
  const { openConnection } = useConnection();
  return (
    <section className="workspace-welcome" aria-labelledby="welcome-title">
      <div className="welcome-main">
        <div className="welcome-copy">
          <div className="section-label">EYES / EXECUTION & EVIDENCE</div>
          <h2 id="welcome-title">
            从测试结果，
            <br />
            回到执行证据。
          </h2>
          <p>
            接入你的 Agent，固定测试与评分版本。
            <br />
            在同一个空间审阅执行过程、评分依据和迭代变化。
          </p>
          <div className="welcome-actions">
            <button className="button primary" onClick={openConnection}>
              <Plug size={16} />
              连接实验空间
              <ArrowRight size={16} />
            </button>
            <Link className="text-button" to="/guide">
              查看接入指南
              <ArrowRight size={15} />
            </Link>
          </div>
          <span className="welcome-note">
            使用项目令牌连接 · 凭据仅保留在当前页面
          </span>
        </div>
        <div
          className="evidence-map"
          aria-label="工作流程：任务输入经过 Agent 执行，生成可审阅的结果与证据。观测范围取决于目标接入。"
        >
          <div className="map-caption">
            <span>工作流程</span>
            <span>INPUT → EXECUTION → EVIDENCE</span>
          </div>
          <div className="map-stage">
            <svg viewBox="0 0 400 220" aria-hidden="true" className="map-lines">
              <circle cx="200" cy="110" r="78" />
              <circle cx="200" cy="110" r="99" />
              <path d="M32 110H150M250 110H368M245 84H300V42H368M245 136H300V178H368" />
              <path d="M200 11V30M200 190V209M101 110H120M280 110H299" />
            </svg>
            <div className="map-input">
              <span>01</span>
              <strong>任务输入</strong>
            </div>
            <div className="map-eye">
              <Eye />
              <span>AGENT</span>
            </div>
            <div className="map-output">
              <span>
                <i />
                执行事件
              </span>
              <span>
                <i />
                任务结果
              </span>
              <span>
                <i />
                评分证据
              </span>
            </div>
          </div>
          <div className="map-footnote">
            观测范围由接入能力决定，每条结论保留证据来源。
          </div>
        </div>
      </div>
      <SetupSteps />
    </section>
  );
}
