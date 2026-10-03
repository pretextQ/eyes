import { formatDate, shortId } from "../format";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  ArrowUpRight,
  FlaskConical,
  Plus,
  RefreshCw,
  Search,
} from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
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
  Metrics,
  PageHeading,
  Pagination,
  SetupSteps,
} from "../components/ui";
import type {
  Experiment,
  ExperimentRequest,
  Operations,
  TargetContent,
} from "../types";

export function ExperimentsPage() {
  const { api, openConnection } = useConnection();
  const [createOpen, setCreateOpen] = useState(false);
  const [params, setParams] = useSearchParams();
  const pageValue = Number(params.get("page"));
  const page =
    Number.isSafeInteger(pageValue) && pageValue >= 0 ? pageValue : 0;
  const search = params.get("q") || "";
  const filter = params.get("status") || "all";
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
  const operations = useQuery({
    queryKey: ["operations"],
    queryFn: ({ signal }) =>
      api!.request<Operations>("/v1/operations", { signal }),
    enabled: !!api,
    refetchInterval: 10000,
  });
  const datasets = useQuery({
    queryKey: ["catalog", "datasets"],
    queryFn: ({ signal }) => api!.catalog("datasets", signal),
    enabled: !!api,
  });
  const items = query.data?.items.slice(0, 50) || [];
  const shown = items.filter(
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
  );
  const counts = operations.data?.work_counts;
  const count = (statuses: string[]) =>
    counts
      ?.filter((w) => statuses.includes(w.status))
      .reduce((n, w) => n + w.count, 0) ?? "—";
  const create = () => (api ? setCreateOpen(true) : openConnection());
  return (
    <>
      <PageHeading
        eyebrow="01 / EXPERIMENTS"
        title="实验工作台"
        description="固定版本，运行测试，从每一条结果回到执行证据。"
        action={
          api && (
            <button className="button primary" onClick={create}>
              <Plus size={17} />
              创建实验
            </button>
          )
        }
      />
      {!api ? (
        <WorkspaceWelcome />
      ) : (
        <>
          <Metrics
            items={[
              {
                label: "本页实验",
                value: query.data
                  ? items.length.toString().padStart(2, "0")
                  : "—",
                note: "按创建时间排列",
              },
              {
                label: "已领取工作",
                value: count(["claimed"]),
                note: "执行与评分工作合计",
                accent: true,
              },
              {
                label: "等待调度",
                value: count(["queued"]),
                note: "项目内排队工作",
              },
              {
                label: "结果未知",
                value: count(["unknown"]),
                note: "需核对实际执行状态",
              },
            ]}
          />
          {operations.error && (
            <ErrorNotice
              error={operations.error}
              retry={() => void operations.refetch()}
            />
          )}
          <section className="panel experiments-panel">
            <div className="panel-toolbar">
              <div className="tabs" aria-label="实验状态筛选">
                {[
                  { id: "all", text: "全部实验" },
                  { id: "active", text: "进行中" },
                  { id: "finished", text: "已结束" },
                  { id: "unresolved", text: "未解决" },
                ].map((f) => (
                  <button
                    key={f.id}
                    aria-pressed={filter === f.id}
                    className={filter === f.id ? "selected" : ""}
                    onClick={() => setFilter(f.id)}
                  >
                    {f.text}
                    {f.id === "all" && query.data && (
                      <span>{items.length}</span>
                    )}
                  </button>
                ))}
              </div>
              <div className="toolbar-tools">
                <div className="search">
                  <Search size={15} />
                  <input
                    aria-label="搜索当前页实验"
                    placeholder="搜索当前页实验…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
                <button
                  className="icon-button"
                  disabled={!api || query.isFetching}
                  aria-label="刷新实验"
                  onClick={() => void query.refetch()}
                >
                  <RefreshCw
                    size={16}
                    className={query.isFetching ? "spin" : ""}
                  />
                </button>
              </div>
            </div>
            {query.isPending ? (
              <Loading />
            ) : query.error ? (
              <ErrorNotice
                error={query.error}
                retry={() => void query.refetch()}
              />
            ) : !items.length ? (
              <Empty
                title="你的第一场实验，从这里开始"
                description="选择目标 Agent、测试集和评分口径，创建一份可追溯的执行记录。"
                action={
                  <button className="button primary" onClick={create}>
                    <FlaskConical size={16} />
                    创建第一场实验
                    <ArrowRight size={16} />
                  </button>
                }
              />
            ) : !shown.length ? (
              <Empty
                compact
                title="没有匹配的实验"
                description="试试其他关键词或状态；搜索范围为当前页。"
                action={
                  <button
                    className="button"
                    onClick={() => {
                      const next = new URLSearchParams(params);
                      next.delete("q");
                      next.delete("status");
                      setParams(next);
                    }}
                  >
                    清除筛选
                  </button>
                }
              />
            ) : (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>实验 / 目标</th>
                      <th>测试集</th>
                      <th>状态</th>
                      <th>执行配置</th>
                      <th>创建时间</th>
                      <th>
                        <span className="sr-only">查看详情</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {shown.map((exp) => (
                      <tr key={exp.id}>
                        <td>
                          <Link
                            className="table-title"
                            to={`/experiments/${exp.id}`}
                            state={{ experimentList: params.toString() }}
                          >
                            {exp.snapshot.target.content.name}
                            <ArrowUpRight size={14} />
                          </Link>
                          <small className="mono">
                            {shortId(exp.id)} ·{" "}
                            {exp.snapshot.target.content.external_version ||
                              "外部版本未知"}
                          </small>
                        </td>
                        <td>
                          {datasets.data?.find((d) => d.id === exp.dataset_id)
                            ?.name || shortId(exp.dataset_id)}
                          <small className="mono">
                            {exp.snapshot.dataset_digest.slice(0, 10)}
                          </small>
                        </td>
                        <td>
                          <Badge status={exp.status} />
                        </td>
                        <td>
                          {exp.snapshot.request.concurrency} 并发
                          <small>
                            {exp.snapshot.request.repetitions} 次重复 ·{" "}
                            {exp.snapshot.request.timeout_seconds}s 超时
                          </small>
                        </td>
                        <td className="date-cell">
                          {formatDate(exp.created_at)}
                        </td>
                        <td>
                          <Link
                            className="icon-button"
                            to={`/experiments/${exp.id}`}
                            state={{ experimentList: params.toString() }}
                            aria-label={`查看实验 ${shortId(exp.id)}`}
                          >
                            <ArrowRight size={17} />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {api && query.data && (
              <Pagination
                page={page}
                next={query.data.items.length > 50}
                onPage={setPage}
              />
            )}
          </section>
          <SetupSteps />
        </>
      )}
      {createOpen && <CreateExperiment onClose={() => setCreateOpen(false)} />}
    </>
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
