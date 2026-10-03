import { lazy, Suspense, useEffect, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Search, Plug, Unplug, X } from "lucide-react";
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
import { Dialog, ErrorNotice, Eye, Loading } from "./components/ui";
import {
  Field,
  FieldGroup,
  FieldLabel,
  FieldDescription,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";

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
  const [quickOpen, setQuickOpen] = useState(false);
  const queryClient = useQueryClient();
  const location = useLocation();
  const current = navigation.find((item) =>
    location.pathname.startsWith(item.url),
  );
  const pageName = location.pathname.includes("/cases/")
    ? "执行审阅"
    : current?.text || "Eyes";
  useEffect(() => {
    document.title = `${pageName} · Eyes`;
  }, [pageName]);
  function connect(client: Api | null) {
    queryClient.clear();
    setApi(client);
    setConnectionOpen(false);
  }
  const openConnection = () => setConnectionOpen(true);
  return (
    <ConnectionContext.Provider value={{ api, openConnection }}>
      <TooltipProvider>
        <a className="skip-link" href="#main">
          跳转到主内容
        </a>
        <SidebarProvider
          style={
            {
              "--sidebar-width": "14rem",
              "--sidebar-width-icon": "3.5rem",
            } as CSSProperties
          }
        >
          <WorkspaceShell
            api={api}
            pageName={pageName}
            openConnection={openConnection}
            quickOpen={quickOpen}
            setQuickOpen={setQuickOpen}
          >
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
          </WorkspaceShell>
        </SidebarProvider>
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
      </TooltipProvider>
    </ConnectionContext.Provider>
  );
}

function WorkspaceShell({
  api,
  pageName,
  openConnection,
  quickOpen,
  setQuickOpen,
  children,
}: {
  api: Api | null;
  pageName: string;
  openConnection: () => void;
  quickOpen: boolean;
  setQuickOpen: React.Dispatch<React.SetStateAction<boolean>>;
  children: ReactNode;
}) {
  const { isMobile, open, openMobile, setOpenMobile } = useSidebar();
  const location = useLocation();
  useEffect(() => {
    function onKeyDown(event: globalThis.KeyboardEvent) {
      if (
        (event.metaKey || event.ctrlKey) &&
        event.key.toLowerCase() === "k" &&
        !event.isComposing
      ) {
        if (
          openMobile ||
          (!quickOpen &&
            document.querySelector('[role="dialog"], dialog[open]'))
        )
          return;
        event.preventDefault();
        setQuickOpen((value) => !value);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [openMobile, quickOpen, setQuickOpen]);
  function connect() {
    setOpenMobile(false);
    openConnection();
  }
  return (
    <>
      <Sidebar collapsible="icon" aria-label="工作空间导航">
        <SidebarHeader className="gap-4 px-3 py-4 group-data-[collapsible=icon]:px-2">
          <div className="flex items-center justify-between gap-2">
            <NavLink
              to="/experiments"
              className="console-brand"
              aria-label="Eyes 实验工作台"
              onClick={() => setOpenMobile(false)}
            >
              <Eye />
              <span className="group-data-[collapsible=icon]:hidden">
                eyes.
              </span>
            </NavLink>
            {isMobile && (
              <Button
                variant="ghost"
                size="icon"
                aria-label="关闭导航"
                onClick={() => setOpenMobile(false)}
              >
                <X />
              </Button>
            )}
          </div>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton
                size="lg"
                variant="outline"
                tooltip="项目连接"
                onClick={connect}
                aria-label="项目连接"
              >
                <Plug />
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span>项目连接</span>
                  <span className="console-project-note">
                    {api ? "已认证" : "尚未连接"}
                  </span>
                </span>
                <ChevronDown className="ml-auto group-data-[collapsible=icon]:hidden" />
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarHeader>
        <SidebarContent>
          <nav aria-label="主导航">
            {navigationGroups.map((group) => (
              <SidebarGroup key={group}>
                <SidebarGroupLabel>{group}</SidebarGroupLabel>
                <SidebarGroupContent>
                  <SidebarMenu>
                    {navigation
                      .filter((item) => item.group === group)
                      .map((item) => (
                        <SidebarMenuItem key={item.url}>
                          <SidebarMenuButton
                            render={<NavLink to={item.url} />}
                            isActive={location.pathname.startsWith(item.url)}
                            tooltip={item.text}
                            onClick={() => setOpenMobile(false)}
                          >
                            <item.icon />
                            <span>{item.text}</span>
                          </SidebarMenuButton>
                        </SidebarMenuItem>
                      ))}
                  </SidebarMenu>
                </SidebarGroupContent>
              </SidebarGroup>
            ))}
          </nav>
        </SidebarContent>
        <SidebarFooter className="px-4 py-4 group-data-[collapsible=icon]:hidden">
          <div className="console-version">
            <span>Eyes Console</span>
            <span>v0.1</span>
          </div>
        </SidebarFooter>
      </Sidebar>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="console-topbar flex h-14 shrink-0 items-center justify-between gap-3 border-b px-4 md:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <SidebarTrigger
              aria-label={
                isMobile ? "打开导航" : open ? "收起侧栏" : "展开侧栏"
              }
              aria-expanded={isMobile ? openMobile : open}
            />
            <Breadcrumb>
              <BreadcrumbList>
                <BreadcrumbItem className="hidden sm:block">
                  工作空间
                </BreadcrumbItem>
                <BreadcrumbSeparator className="hidden sm:block" />
                <BreadcrumbItem>
                  <BreadcrumbPage>{pageName}</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>
          <div className="flex shrink-0 items-center gap-2 md:gap-3">
            <Button
              variant="ghost"
              size="icon"
              aria-label="快速导航"
              title="快速导航（⌘ K / Ctrl K）"
              aria-keyshortcuts="Meta+k Control+k"
              onClick={() => setQuickOpen(true)}
            >
              <Search />
            </Button>
            <span
              className="console-connection hidden sm:inline-flex"
              data-connected={!!api}
            >
              <i />
              {api ? "已认证" : "未连接"}
            </span>
            <Button
              variant="outline"
              onClick={openConnection}
              aria-label="连接设置"
            >
              <Plug data-icon="inline-start" />
              <span className="hidden sm:inline">连接设置</span>
              <span className="sm:hidden">连接</span>
            </Button>
          </div>
        </header>
        <main
          id="main"
          tabIndex={-1}
          className="console-main mx-0 w-full min-w-0 max-w-none px-4 py-6 md:px-6 md:py-7"
        >
          {children}
        </main>
      </div>
    </>
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
      title="连接项目"
      subtitle="验证项目令牌后加载实验数据。"
      onClose={onClose}
    >
      <form onSubmit={submit} className="form">
        <FieldGroup>
          <Field data-disabled={busy} data-invalid={error != null}>
            <FieldLabel htmlFor="project-token">项目令牌</FieldLabel>
            <Input
              id="project-token"
              data-autofocus
              type="password"
              disabled={busy}
              required
              autoComplete="off"
              aria-invalid={error != null}
              placeholder="输入 Bearer 令牌"
              value={token}
              onChange={(event) => setToken(event.target.value)}
            />
            <FieldDescription>
              支持 read 与 manage 令牌。刷新页面后需重新连接。
            </FieldDescription>
          </Field>
        </FieldGroup>
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
            <Button
              variant="destructive"
              type="button"
              onClick={() => onConnect(null)}
            >
              <Unplug data-icon="inline-start" />
              断开连接
            </Button>
          )}
          <Button type="button" variant="outline" onClick={onClose}>
            取消
          </Button>
          <Button type="submit" disabled={busy || !token.trim()}>
            {busy ? "正在验证…" : "连接项目"}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
