import { lazy, Suspense, useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowUpRight,
  ChevronDown,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Plug,
  Plus,
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
import { navigation, navigationGroups } from "./navigation";
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

const QuickNavigation = lazy(() =>
  import("./components/QuickNavigation").then((module) => ({
    default: module.QuickNavigation,
  })),
);

export default function App() {
  const [api, setApi] = useState<Api | null>(null);
  const [connectionOpen, setConnectionOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [quickOpen, setQuickOpen] = useState(false);
  useEffect(() => {
    function onKeyDown(event: globalThis.KeyboardEvent) {
      if (
        (event.metaKey || event.ctrlKey) &&
        event.key.toLowerCase() === "k" &&
        !event.isComposing
      ) {
        if (
          mobileOpen ||
          (!quickOpen && document.querySelector("dialog[open]"))
        )
          return;
        event.preventDefault();
        setQuickOpen((open) => !open);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [mobileOpen, quickOpen]);
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
  const current = navigation.find((n) => location.pathname.startsWith(n.url));
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
      <div className={`app-shell ${collapsed ? "sidebar-collapsed" : ""}`}>
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
            aria-label="Eyes 实验工作台"
            onClick={() => setMobileOpen(false)}
          >
            <Eye />
            <span>
              eyes<span className="brand-dot">.</span>
            </span>
          </NavLink>
          <button
            className="workspace-switch"
            aria-label="连接实验空间"
            title="连接实验空间"
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
          <nav aria-label="主导航">
            {navigationGroups.map((group) => (
              <div className="nav-group" key={group}>
                <div className="nav-label">{group}</div>
                {navigation
                  .filter((item) => item.group === group)
                  .map((item) => (
                    <NavLink
                      key={item.url}
                      to={item.url}
                      title={item.text}
                      aria-label={item.text}
                      onClick={() => setMobileOpen(false)}
                      className={({ isActive }) =>
                        `nav-item ${isActive ? "selected" : ""}`
                      }
                    >
                      <item.icon size={18} strokeWidth={1.7} />
                      <span>{item.text}</span>
                    </NavLink>
                  ))}
              </div>
            ))}
          </nav>
          <div className="sidebar-bottom">
            <NavLink
              className="sidebar-help"
              to="/guide"
              onClick={() => setMobileOpen(false)}
            >
              <Plug size={16} />
              <span>接入与使用帮助</span>
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
                className="icon-button sidebar-toggle"
                onClick={() => setCollapsed(!collapsed)}
                aria-label={collapsed ? "展开侧栏" : "收起侧栏"}
                title={collapsed ? "展开侧栏" : "收起侧栏"}
                aria-expanded={!collapsed}
                aria-controls="sidebar"
              >
                {collapsed ? (
                  <PanelLeftOpen size={18} />
                ) : (
                  <PanelLeftClose size={18} />
                )}
              </button>
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
              <button
                className="quick-trigger"
                onClick={() => setQuickOpen(true)}
                aria-label="快速导航"
                aria-keyshortcuts="Meta+k Control+k"
                title="快速导航（⌘ K / Ctrl K）"
              >
                <Search size={15} />
                <span>快速导航</span>
                <kbd>⌘ K</kbd>
              </button>
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
      {quickOpen && (
        <Suspense fallback={<Loading label="正在打开快速导航" />}>
          <QuickNavigation
            onClose={() => setQuickOpen(false)}
            onConnect={() => {
              setQuickOpen(false);
              setConnectionOpen(true);
            }}
          />
        </Suspense>
      )}
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
