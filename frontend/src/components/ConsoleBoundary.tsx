import { Component } from "react";
import type { ReactNode } from "react";
import { AlertCircle, RefreshCw } from "lucide-react";

export class ConsoleBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="not-found">
        <AlertCircle size={32} />
        <h1>页面暂时无法显示</h1>
        <p className="muted">
          刷新后重新连接项目；如果持续出现，请检查 API 响应与浏览器控制台。
        </p>
        <button
          className="button primary"
          onClick={() => window.location.reload()}
        >
          <RefreshCw size={16} />
          刷新页面
        </button>
      </div>
    );
  }
}
