import { formatDate, shortId } from "../format";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  ArrowUpRight,
  FlaskConical,
  Plus,
  RefreshCw,
  SlidersHorizontal,
  Check,
  Target,
  Layers3,
  ClipboardCheck,
  Search,
  X,
} from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  InputGroup,
  InputGroupInput,
  InputGroupAddon,
} from "@/components/ui/input-group";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableHeader,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
} from "@/components/ui/table";
import { WorkspaceWelcome } from "../components/WorkspaceWelcome";
import { useConnection } from "../connection";
import {
  Badge,
  CheckItem,
  Dialog,
  Disconnected,
  Empty,
  ErrorNotice,
  Field,
  Loading,
  TableLoading,
  PageHeading,
  Pagination,
} from "../components/ui";
import type { Experiment, ExperimentRequest, TargetContent } from "../types";

export function ExperimentsPage() {
  const { api, openConnection } = useConnection();
  const [createOpen, setCreateOpen] = useState(false);
  const [params, setParams] = useSearchParams();
  const pageValue = Number(params.get("page"));
  const page =
    Number.isSafeInteger(pageValue) && pageValue >= 0 ? pageValue : 0;
  const search = params.get("q") || "";
  const filter = ["all", "active", "finished", "unresolved"].includes(
    params.get("status") || "",
  )
    ? params.get("status")!
    : "all";
  const sort = params.get("sort") === "oldest" ? "oldest" : "newest";
  const compact = params.get("density") === "compact";
  function update(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: key === "q" });
  }
  const setPage = (value: number) => update("page", String(value));
  const setSearch = (value: string) => update("q", value);
  const setFilter = (value: string) => update("status", value);
  const query = useQuery({
    queryKey: ["experiments", page],
    queryFn: ({ signal }) =>
      api!.request<{ items: Experiment[] }>(
        `/v1/experiments?limit=51&offset=${page * 50}`,
        { signal },
      ),
    enabled: !!api,
    refetchInterval: 10000,
  });
  const datasets = useQuery({
    queryKey: ["catalog", "datasets"],
    queryFn: ({ signal }) => api!.catalog("datasets", signal),
    enabled: !!api,
  });
  const items = query.data?.items.slice(0, 50) || [];
  const shown = items
    .filter(
      (e) =>
        `${e.id} ${e.snapshot.target.content.name} ${e.snapshot.target.content.external_version || ""}`
          .toLowerCase()
          .includes(search.toLowerCase()) &&
        (filter === "all" ||
          (filter === "active"
            ? ["queued", "running", "cancel_requested"].includes(e.status)
            : filter === "unresolved"
              ? e.status === "completed_with_unresolved"
              : ["completed", "cancelled"].includes(e.status))),
    )
    .sort((a, b) =>
      sort === "oldest"
        ? Date.parse(a.created_at) - Date.parse(b.created_at)
        : Date.parse(b.created_at) - Date.parse(a.created_at),
    );
  function clearFilters() {
    const next = new URLSearchParams(params);
    next.delete("q");
    next.delete("status");
    setParams(next);
  }
  const create = () => (api ? setCreateOpen(true) : openConnection());
  return (
    <>
      <PageHeading
        eyebrow=""
        title="实验"
        description="查看固定配置、执行状态和用例结果。"
        action={
          api && (
            <>
              <Link className="button" to="/batches">
                多 Agent 批次
              </Link>
              <Button onClick={create}>
                <Plus data-icon="inline-start" />
                创建实验
              </Button>
            </>
          )
        }
      />
      {!api ? (
        <WorkspaceWelcome />
      ) : (
        <section className="experiment-list" aria-label="实验列表">
          {(query.isPending || query.isError || items.length > 0) && (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3 pb-4">
                <ToggleGroup
                  value={[filter]}
                  onValueChange={(values) => {
                    if (values[0]) setFilter(values[0]);
                  }}
                  aria-label="实验状态筛选"
                  disabled={query.isPending}
                  spacing={1}
                >
                  {[
                    { id: "all", text: "全部" },
                    { id: "active", text: "进行中" },
                    { id: "finished", text: "已结束" },
                    { id: "unresolved", text: "未解决" },
                  ].map((item) => (
                    <ToggleGroupItem key={item.id} value={item.id}>
                      {item.text}
                    </ToggleGroupItem>
                  ))}
                </ToggleGroup>
                <div className="flex w-full items-center gap-2 sm:w-auto">
                  <InputGroup className="min-w-0 flex-1 sm:w-56">
                    <InputGroupInput
                      type="search"
                      aria-label="搜索当前页实验"
                      placeholder="搜索当前页实验…"
                      value={search}
                      disabled={query.isPending}
                      onChange={(event) => setSearch(event.target.value)}
                    />
                    <InputGroupAddon>
                      <Search />
                    </InputGroupAddon>
                  </InputGroup>
                  <DropdownMenu>
                    <DropdownMenuTrigger render={<Button variant="outline" />}>
                      <SlidersHorizontal data-icon="inline-start" />
                      显示
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-44">
                      <DropdownMenuGroup>
                        <DropdownMenuLabel>当前页排序</DropdownMenuLabel>
                        <DropdownMenuRadioGroup
                          value={sort}
                          onValueChange={(value) => update("sort", value)}
                        >
                          <DropdownMenuRadioItem value="newest">
                            最新创建优先
                          </DropdownMenuRadioItem>
                          <DropdownMenuRadioItem value="oldest">
                            最早创建优先
                          </DropdownMenuRadioItem>
                        </DropdownMenuRadioGroup>
                      </DropdownMenuGroup>
                      <DropdownMenuSeparator />
                      <DropdownMenuGroup>
                        <DropdownMenuLabel>列表密度</DropdownMenuLabel>
                        <DropdownMenuRadioGroup
                          value={compact ? "compact" : "comfortable"}
                          onValueChange={(value) => update("density", value)}
                        >
                          <DropdownMenuRadioItem value="comfortable">
                            标准
                          </DropdownMenuRadioItem>
                          <DropdownMenuRadioItem value="compact">
                            紧凑
                          </DropdownMenuRadioItem>
                        </DropdownMenuRadioGroup>
                      </DropdownMenuGroup>
                    </DropdownMenuContent>
                  </DropdownMenu>
                  <Button
                    variant="ghost"
                    size="icon"
                    disabled={query.isFetching}
                    aria-label="刷新实验"
                    onClick={() => void query.refetch()}
                  >
                    <RefreshCw className={cn(query.isFetching && "spin")} />
                  </Button>
                </div>
              </div>
              {(search || filter !== "all") && shown.length > 0 && (
                <div className="experiment-filter-note" role="status">
                  <span>
                    本页匹配 {shown.length} / {items.length} 条
                  </span>
                  <Button variant="ghost" size="sm" onClick={clearFilters}>
                    <X data-icon="inline-start" />
                    清除筛选
                  </Button>
                </div>
              )}
            </>
          )}
          {datasets.error && items.length > 0 && (
            <ErrorNotice
              error={datasets.error}
              retry={() => void datasets.refetch()}
            />
          )}
          {query.isPending ? (
            <TableLoading label="正在读取实验" />
          ) : query.error ? (
            <ErrorNotice
              error={query.error}
              retry={() => void query.refetch()}
            />
          ) : !items.length ? (
            page > 0 ? (
              <Empty
                title="本页没有实验"
                description="返回上一页查看实验记录。"
                action={
                  <Button variant="outline" onClick={() => setPage(page - 1)}>
                    上一页
                  </Button>
                }
              />
            ) : (
              <ExperimentSetup onCreate={create} />
            )
          ) : !shown.length ? (
            <Empty
              compact
              icon={Search}
              title="没有匹配的实验"
              description="搜索范围为当前页，试试其他关键词或状态。"
              action={
                <Button variant="outline" onClick={clearFilters}>
                  清除筛选
                </Button>
              }
            />
          ) : (
            <div
              className="experiment-table-region"
              data-density={compact ? "compact" : "comfortable"}
            >
              <Table
                containerProps={{
                  role: "region",
                  "aria-label": "实验记录，可横向滚动",
                  tabIndex: 0,
                }}
              >
                <caption className="sr-only">
                  当前页实验，按创建时间
                  {sort === "newest" ? "从新到旧" : "从旧到新"}排列
                </caption>
                <TableHeader>
                  <TableRow>
                    <TableHead>实验 / 目标</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>测试集</TableHead>
                    <TableHead>执行配置</TableHead>
                    <TableHead>创建时间</TableHead>
                    <TableHead>
                      <span className="sr-only">查看详情</span>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {shown.map((exp) => (
                    <TableRow
                      key={exp.id}
                      className={cn("h-14", compact && "h-10 [&>td]:py-1")}
                    >
                      <TableCell>
                        <Link
                          className="experiment-name"
                          to={`/experiments/${exp.id}`}
                          state={{ experimentList: params.toString() }}
                        >
                          {exp.snapshot.target.content.name}
                        </Link>
                        <span className="experiment-subline">
                          <code>{shortId(exp.id)}</code>
                          <span>·</span>
                          <span>
                            {exp.snapshot.target.content.external_version ||
                              "外部版本未知"}
                          </span>
                        </span>
                      </TableCell>
                      <TableCell>
                        <Badge status={exp.status} />
                      </TableCell>
                      <TableCell>
                        <span className="experiment-dataset">
                          {datasets.data?.find(
                            (item) => item.id === exp.dataset_id,
                          )?.name || shortId(exp.dataset_id)}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className="experiment-config">
                          {exp.snapshot.request.concurrency} 并发<span>·</span>
                          {exp.snapshot.request.repetitions} 次重复
                          <span>·</span>
                          {exp.snapshot.request.timeout_seconds}s
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className="experiment-date">
                          {formatDate(exp.created_at)}
                        </span>
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size={compact ? "icon-xs" : "icon"}
                          nativeButton={false}
                          render={
                            <Link
                              to={`/experiments/${exp.id}`}
                              state={{ experimentList: params.toString() }}
                            />
                          }
                          aria-label={`查看实验 ${shortId(exp.id)}`}
                        >
                          <ArrowRight />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
          {query.data && items.length > 0 && (
            <div className="experiment-list-footer">
              <span className="experiment-sync">
                本页 {shown.length} 条 ·{" "}
                {query.isFetching
                  ? "正在同步…"
                  : query.isError
                    ? "同步失败"
                    : "每 10 秒更新"}
              </span>
              <Pagination
                page={page}
                next={query.data.items.length > 50}
                onPage={setPage}
              />
            </div>
          )}
        </section>
      )}
      {createOpen && <CreateExperiment onClose={() => setCreateOpen(false)} />}
    </>
  );
}

function ExperimentSetup({ onCreate }: { onCreate: () => void }) {
  const { api } = useConnection();
  const targets = useQuery({
    queryKey: ["catalog", "targets"],
    queryFn: ({ signal }) => api!.catalog("targets", signal),
    enabled: !!api,
  });
  const datasets = useQuery({
    queryKey: ["catalog", "datasets"],
    queryFn: ({ signal }) => api!.catalog("datasets", signal),
    enabled: !!api,
  });
  const scorers = useQuery({
    queryKey: ["catalog", "scorers"],
    queryFn: ({ signal }) => api!.catalog("scorers", signal),
    enabled: !!api,
  });
  if (targets.isPending || datasets.isPending || scorers.isPending)
    return <Loading label="正在检查实验配置" />;
  if (targets.error || datasets.error || scorers.error)
    return (
      <ErrorNotice
        error={targets.error || datasets.error || scorers.error}
        retry={() => {
          void targets.refetch();
          void datasets.refetch();
          void scorers.refetch();
        }}
      />
    );
  const steps = [
    {
      name: "目标 Agent",
      description: "发布 HTTP 或 Python 接入版本",
      to: "/targets",
      count: targets.data.length,
      icon: Target,
    },
    {
      name: "测试集",
      description: "导入 JSONL 测试用例",
      to: "/datasets",
      count: datasets.data.length,
      icon: Layers3,
    },
    {
      name: "评分口径",
      description: "发布规则或 Python 评分器",
      to: "/scorers",
      count: scorers.data.length,
      icon: ClipboardCheck,
    },
  ];
  const next = steps.find((step) => step.count === 0);
  return (
    <div className="experiment-setup">
      <Empty
        icon={FlaskConical}
        title="尚无实验"
        description={
          next
            ? "先准备目标、测试集和评分口径，再创建实验。"
            : "目标、测试集和评分口径已就绪。"
        }
        action={
          next ? (
            <Button nativeButton={false} render={<Link to={next.to} />}>
              配置{next.name}
            </Button>
          ) : (
            <Button onClick={onCreate}>
              <Plus data-icon="inline-start" />
              创建实验
            </Button>
          )
        }
      />
      <ul className="experiment-setup-list">
        {steps.map((step) => (
          <li key={step.to}>
            <Link to={step.to}>
              <step.icon />
              <span>
                <strong>{step.name}</strong>
                <small>{step.description}</small>
              </span>
              <span className="setup-availability">
                {step.count > 0 ? (
                  <>
                    <Check />
                    {step.count} 个版本
                  </>
                ) : (
                  "待配置"
                )}
              </span>
              <ArrowRight />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function CreateExperiment({
  onClose,
  source,
}: {
  onClose: () => void;
  source?: Experiment;
}) {
  const { api } = useConnection();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const targets = useQuery({
    queryKey: ["catalog", "targets"],
    queryFn: ({ signal }) => api!.catalog("targets", signal),
    enabled: !!api,
  });
  const datasets = useQuery({
    queryKey: ["catalog", "datasets"],
    queryFn: ({ signal }) => api!.catalog("datasets", signal),
    enabled: !!api,
  });
  const scorers = useQuery({
    queryKey: ["catalog", "scorers"],
    queryFn: ({ signal }) => api!.catalog("scorers", signal),
    enabled: !!api,
  });
  const [target, setTarget] = useState(source?.target_id || "");
  const [dataset, setDataset] = useState(source?.dataset_id || "");
  const [selected, setSelected] = useState<string[]>(
    source?.snapshot.request.scorer_version_ids || [],
  );
  const [concurrency, setConcurrency] = useState(
    source?.snapshot.request.concurrency || 1,
  );
  const [timeout, setTimeout] = useState(
    source?.snapshot.request.timeout_seconds || 300,
  );
  const [repetitions, setRepetitions] = useState(
    source?.snapshot.request.repetitions || 1,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [requestKey, setRequestKey] = useState<{
    body: string;
    key: string;
  } | null>(null);
  const selectedTarget = targets.data?.find((t) => t.id === target)
    ?.content as unknown as TargetContent | undefined;
  const available =
    targets.data?.length && datasets.data?.length && scorers.data?.length;
  const missing = [
    !targets.data?.length && { label: "目标 Agent", to: "/targets" },
    !datasets.data?.length && { label: "测试集", to: "/datasets" },
    !scorers.data?.length && { label: "评分口径", to: "/scorers" },
  ].filter(Boolean) as { label: string; to: string }[];
  async function submit(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!api) return;
    setBusy(true);
    setError(null);
    const body: ExperimentRequest = {
      target_version_id: target,
      dataset_version_id: dataset,
      scorer_version_ids: selected,
      concurrency,
      timeout_seconds: timeout,
      repetitions,
      attempt_selection: "first_success",
      parent_experiment_id: source?.id || null,
    };
    const serialized = JSON.stringify(body);
    const key =
      requestKey?.body === serialized ? requestKey.key : crypto.randomUUID();
    setRequestKey({ body: serialized, key });
    try {
      const result = await api.post<Experiment>("/v1/experiments", body, {
        "Idempotency-Key": key,
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["experiments"] }),
        queryClient.invalidateQueries({ queryKey: ["comparison-experiments"] }),
        queryClient.invalidateQueries({ queryKey: ["operations"] }),
      ]);
      onClose();
      navigate(`/experiments/${result.id}`);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      title={source ? "创建关联实验" : "创建实验"}
      subtitle="发布时冻结目标、用例和评分配置，历史记录保持可追溯。"
      wide
      onClose={onClose}
    >
      {!api ? (
        <Disconnected />
      ) : targets.isPending || datasets.isPending || scorers.isPending ? (
        <Loading />
      ) : targets.error || datasets.error || scorers.error ? (
        <ErrorNotice
          error={targets.error || datasets.error || scorers.error}
          retry={() => {
            void targets.refetch();
            void datasets.refetch();
            void scorers.refetch();
          }}
        />
      ) : !available ? (
        <div className="form">
          <Empty
            compact
            title="先准备实验所需版本"
            description="实验至少需要一个目标、一份测试集和一个评分器。"
          />
          {missing.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className="setup-link"
              onClick={onClose}
            >
              配置{item.label}
              <ArrowUpRight size={16} />
            </Link>
          ))}
        </div>
      ) : (
        <form className="form" onSubmit={submit}>
          <div className="form-step">
            <span>01</span>
            <h3>选择固定版本</h3>
          </div>
          <div className="form-grid">
            <Field label="目标 Agent">
              <select
                required
                value={target}
                onChange={(e) => {
                  setTarget(e.target.value);
                  setConcurrency(1);
                }}
              >
                <option value="">选择目标版本</option>
                {targets.data?.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} ·{" "}
                    {String(t.content.external_version || t.digest.slice(0, 8))}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="测试集">
              <select
                required
                value={dataset}
                onChange={(e) => setDataset(e.target.value)}
              >
                <option value="">选择测试集版本</option>
                {datasets.data?.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} · {d.digest.slice(0, 8)}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <fieldset className="scorer-picker">
            <legend>评分口径（至少一项）</legend>
            {scorers.data?.map((s) => (
              <CheckItem
                key={s.id}
                checked={selected.includes(s.id)}
                onChange={(checked) =>
                  setSelected((v) =>
                    checked ? [...v, s.id] : v.filter((id) => id !== s.id),
                  )
                }
              >
                <span>
                  {s.name}
                  <small className="mono">{s.digest.slice(0, 8)}</small>
                </span>
              </CheckItem>
            ))}
          </fieldset>
          <div className="form-step">
            <span>02</span>
            <h3>执行配置</h3>
          </div>
          <div className="form-grid three">
            <Field
              label="并发数"
              hint={
                selectedTarget
                  ? `目标容量上限 ${selectedTarget.concurrency_limit}`
                  : "先选择目标"
              }
            >
              <input
                required
                type="number"
                min={1}
                max={selectedTarget?.concurrency_limit || 1}
                value={concurrency}
                onChange={(e) => setConcurrency(Number(e.target.value))}
              />
            </Field>
            <Field label="单任务超时 / 秒">
              <input
                required
                type="number"
                min={1}
                max={86400}
                value={timeout}
                onChange={(e) => setTimeout(Number(e.target.value))}
              />
            </Field>
            <Field label="每用例重复次数">
              <input
                required
                type="number"
                min={1}
                max={100}
                value={repetitions}
                onChange={(e) => setRepetitions(Number(e.target.value))}
              />
            </Field>
          </div>
          <div className="notice">
            <p>
              评分选择固定为首个执行成功的尝试；此前失败保留在历史中。
              {source && (
                <>
                  关联来源：<code>{shortId(source.id)}</code>。
                </>
              )}
            </p>
          </div>
          <div className="submission-summary" aria-label="提交前配置摘要">
            <span className="section-label">将冻结的配置</span>
            <strong>
              {targets.data?.find((t) => t.id === target)?.name || "请选择目标"}{" "}
              <span>→</span>{" "}
              {datasets.data?.find((d) => d.id === dataset)?.name ||
                "请选择测试集"}
            </strong>
            <p>
              {selected.length} 项评分口径 · {concurrency} 并发 · {repetitions}{" "}
              次重复 · {timeout}s 单任务超时
            </p>
          </div>
          {error != null && <ErrorNotice error={error} />}
          <div className="form-actions">
            <button type="button" className="button" onClick={onClose}>
              取消
            </button>
            <button
              className="button primary"
              disabled={busy || !target || !dataset || !selected.length}
            >
              <Plus size={16} />
              {busy ? "正在创建…" : "创建并入队"}
            </button>
          </div>
        </form>
      )}
    </Dialog>
  );
}
