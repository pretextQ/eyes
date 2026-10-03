import { lazy, Suspense, useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowUpRight,
  ChevronDown,
  CircleHelp,
  FlaskConical,
  GitCompareArrows,
  Layers3,
  Menu,
  Plug,
  Plus,
  SlidersHorizontal,
  Target,
  Unplug,
  X,
} from "lucide-react";
import {
  NavLink,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { Api } from "./api";
import { ConnectionContext } from "./connection";
import { Dialog, ErrorNotice, Eye, Field, Loading } from "./components/ui";
const ExperimentsPage = lazy(() =>
  import("./pages/Experiments").then((module) => ({
    default: module.ExperimentsPage,
  })),
);
const ExperimentPage = lazy(() =>
  import("./pages/Experiment").then((module) => ({
    default: module.ExperimentPage,
  })),
);
const CaseWorkspacePage = lazy(() =>
  import("./pages/CaseWorkspace").then((module) => ({
    default: module.CaseWorkspacePage,
  })),
);
const CatalogPage = lazy(() =>
  import("./pages/Catalog").then((module) => ({ default: module.CatalogPage })),
);
const ComparisonPage = lazy(() =>
  import("./pages/Comparison").then((module) => ({
    default: module.ComparisonPage,
  })),
);
const OperationsPage = lazy(() =>
  import("./pages/Operations").then((module) => ({
    default: module.OperationsPage,
  })),
);
const GuidePage = lazy(() =>
  import("./pages/Guide").then((module) => ({ default: module.GuidePage })),
);

const nav = [
  { url: "/experiments", text: "实验", en: "Experiments", icon: FlaskConical },
  {
    url: "/comparison",
    text: "结果对比",
    en: "Comparison",
    icon: GitCompareArrows,
  },
  { url: "/targets", text: "目标 Agent", en: "Targets", icon: Target },
  { url: "/datasets", text: "测试集", en: "Datasets", icon: Layers3 },
  { url: "/scorers", text: "评分口径", en: "Scorers", icon: SlidersHorizontal },
  { url: "/operations", text: "运行状态", en: "Operations", icon: Activity },
];

export default function App() {
  const [api, setApi] = useState<Api | null>(null);
  const [connectionOpen, setConnectionOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(
    () => window.matchMedia("(max-width: 700px)").matches,
  );
  const sidebarRef = useRef<HTMLElement>(null);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 700px)");
    const update = () => setIsMobile(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  useEffect(() => {
    if (!mobileOpen || !isMobile) return;
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    sidebarRef.current?.querySelector<HTMLElement>("a, button")?.focus();
    return () => {
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, [mobileOpen, isMobile]);
  function handleNavKey(event: KeyboardEvent<HTMLElement>) {
    if (!mobileOpen || !isMobile) return;
    if (event.key === "Escape") {
      setMobileOpen(false);
      return;
    }
    if (event.key !== "Tab") return;
    const elements = sidebarRef.current?.querySelectorAll<HTMLElement>(
      "a[href], button:not(:disabled)",
    );
    if (!elements?.length) return;
    const first = elements[0],
      last = elements[elements.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
  const queryClient = useQueryClient();
  const location = useLocation();
  const current = nav.find((n) => location.pathname.startsWith(n.url));
  const pageName = location.pathname.includes("/cases/")
    ? "执行审阅"
    : current?.text || "接入指南";
  useEffect(() => {
    document.title = `${pageName} · Eyes`;
  }, [pageName]);
  function connect(client: Api | null) {
    queryClient.clear();
    setApi(client);
    setConnectionOpen(false);
  }
  return (
    <ConnectionContext.Provider
      value={{ api, openConnection: () => setConnectionOpen(true) }}
    >
      <a className="skip-link" href="#main">
        跳转到主内容
      </a>
      <div className="app-shell">
        {mobileOpen && (
          <button
            className="nav-overlay"
            aria-label="关闭导航"
            onClick={() => setMobileOpen(false)}
          />
        )}
        <aside
          id="sidebar"
          ref={sidebarRef}
          inert={isMobile && !mobileOpen}
          onKeyDown={handleNavKey}
          className={`sidebar ${mobileOpen ? "mobile-open" : ""}`}
        >
          <NavLink
            to="/experiments"
            className="brand"
            onClick={() => setMobileOpen(false)}
          >
            <Eye />
            <span>
              eyes<span className="brand-dot">.</span>
            </span>
            <span className="brand-caption">AGENT LAB</span>
          </NavLink>
          <button
            className="workspace-switch"
            onClick={() => {
              setMobileOpen(false);
              setConnectionOpen(true);
            }}
          >
            <span className="workspace-mark">E</span>
            <span>
              <strong>实验空间</strong>
              <small>{api ? "已连接项目" : "本地控制台"}</small>
            </span>
            <ChevronDown size={14} />
          </button>
          <div className="nav-label">工作空间</div>
          <nav aria-label="主导航">
            {nav.map((n, i) => (
              <NavLink
                key={n.url}
                to={n.url}
                onClick={() => setMobileOpen(false)}
                className={({ isActive }) =>
                  `nav-item ${isActive ? "selected" : ""} ${i === 2 ? "nav-separator" : ""}`
                }
              >
                <n.icon size={18} strokeWidth={1.6} />
                <span>{n.text}</span>
                {i === 0 && <span className="nav-shortcut">01</span>}
              </NavLink>
            ))}
          </nav>
          <div className="sidebar-bottom">
            <div className="lab-note">
              <span className="section-label">EVIDENCE FIRST</span>
              <p>
                看见执行过程，
                <br />
                让结果有据可查。
              </p>
              <div className="lab-line" />
            </div>
            <NavLink
              to="/guide"
              className="nav-item"
              onClick={() => setMobileOpen(false)}
            >
              <CircleHelp size={18} />
              接入指南
              <ArrowUpRight size={14} />
            </NavLink>
            <div className="sidebar-version">
              <span>Eyes Console</span>
              <span>v0.1</span>
            </div>
          </div>
        </aside>
        <div className="main-shell" inert={isMobile && mobileOpen}>
          <div className="topbar">
            <div className="breadcrumb">
              <button
                className="icon-button mobile-menu"
                onClick={() => setMobileOpen(true)}
                aria-label="打开导航"
                aria-expanded={mobileOpen}
                aria-controls="sidebar"
              >
                <Menu size={20} />
              </button>
              <span>工作空间</span>
              <span className="slash">/</span>
              <strong>{pageName}</strong>
            </div>
            <div className="topbar-actions">
              <span className={`connection-status ${api ? "connected" : ""}`}>
                <i />
                {api ? "已认证连接" : "尚未连接"}
              </span>
              <button
                aria-label="连接设置"
                className="button small connection-button"
                onClick={() => setConnectionOpen(true)}
              >
                <Plug size={14} />
                <span>连接设置</span>
              </button>
            </div>
          </div>
          <main id="main" tabIndex={-1}>
            <Suspense fallback={<Loading label="正在打开页面" />}>
              <Routes>
                <Route
                  path="/"
                  element={<Navigate to="/experiments" replace />}
                />
                <Route path="/experiments" element={<ExperimentsPage />} />
                <Route path="/experiments/:id" element={<ExperimentPage />} />
                <Route
                  path="/experiments/:id/cases/:runId"
                  element={<CaseWorkspacePage />}
                />
                <Route path="/comparison" element={<ComparisonPage />} />
                <Route
                  path="/targets"
                  element={<CatalogPage kind="targets" />}
                />
                <Route
                  path="/datasets"
                  element={<CatalogPage kind="datasets" />}
                />
                <Route
                  path="/scorers"
                  element={<CatalogPage kind="scorers" />}
                />
                <Route path="/operations" element={<OperationsPage />} />
                <Route path="/guide" element={<GuidePage />} />
                <Route
                  path="*"
                  element={
                    <div className="not-found">
                      <h1>页面不存在</h1>
                      <NavLink className="button primary" to="/experiments">
                        返回实验
                      </NavLink>
                    </div>
                  }
                />
              </Routes>
            </Suspense>
          </main>
          <footer className="page-footer">
            <span>
              <span className="footer-dot" /> EYES · AGENT TESTING &
              OBSERVABILITY
            </span>
            <span>执行 · 证据 · 迭代</span>
          </footer>
        </div>
      </div>
      {connectionOpen && (
        <ConnectionDialog
          current={api}
          onClose={() => setConnectionOpen(false)}
          onConnect={connect}
        />
      )}
    </ConnectionContext.Provider>
  );
}
function ConnectionDialog({
  current,
  onClose,
  onConnect,
}: {
  current: Api | null;
  onClose: () => void;
  onConnect: (client: Api | null) => void;
}) {
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const pending = useRef<AbortController | null>(null);
  useEffect(() => () => pending.current?.abort(), []);
  async function submit(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const client = new Api(token.trim());
    const controller = new AbortController();
    pending.current?.abort();
    pending.current = controller;
    try {
      await client.request("/v1/operations", {
        signal: AbortSignal.any([
          controller.signal,
          AbortSignal.timeout(15000),
        ]),
      });
      if (controller.signal.aborted) return;
      onConnect(client);
    } catch (e) {
      if (!controller.signal.aborted) setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      title="连接实验空间"
      subtitle="用项目令牌打开你的实验空间。"
      onClose={onClose}
    >
      <form onSubmit={submit} className="form">
        <Field
          label="项目令牌"
          hint="支持 read 与 manage 令牌。令牌仅保留在当前页面内存中，刷新后需重新连接。"
        >
          <input
            type="password"
            disabled={busy}
            required
            autoComplete="off"
            placeholder="输入 Bearer 令牌"
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
        </Field>
        <details className="connection-help">
          <summary>如何获取项目令牌？</summary>
          <p>
            先启动 PostgreSQL、迁移和 API，再用{" "}
            <code>eyes-admin bootstrap</code> 获取令牌。开发代理默认连接{" "}
            <code>127.0.0.1:8000</code>。
          </p>
        </details>
        {error != null && <ErrorNotice error={error} />}
        <div className="form-actions">
          {current && (
            <button
              type="button"
              className="button danger"
              onClick={() => onConnect(null)}
            >
              <Unplug size={16} />
              断开连接
            </button>
          )}
          <button type="button" className="button" onClick={onClose}>
            <X size={15} />
            取消
          </button>
          <button className="button primary" disabled={busy || !token.trim()}>
            <Plus size={15} />
            {busy ? "正在验证…" : "连接项目"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
