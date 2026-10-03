import { formatDate, formatRatio, shortId } from "../format";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowUpRight,
  GitBranch,
  ListTree,
  Search,
  Square,
  Timer,
} from "lucide-react";
import {
  Link,
  useLocation,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { useConnection } from "../connection";
import {
  Badge,
  Dialog,
  Disconnected,
  Empty,
  ErrorNotice,
  JsonBlock,
  Loading,
  TableLoading,
  Metrics,
  PageHeading,
  Pagination,
} from "../components/ui";
import type { CaseRun, Experiment, Summary } from "../types";
import { CreateExperiment } from "./Experiments";

export function ExperimentPage() {
  const { id } = useParams();
  return <ExperimentView key={id} id={id!} />;
}
function ExperimentView({ id }: { id: string }) {
  const { api } = useConnection();
  const client = useQueryClient();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const pageValue = Number(params.get("page"));
  const page =
    Number.isSafeInteger(pageValue) && pageValue >= 0 ? pageValue : 0;
  function setPage(value: number) {
    const next = new URLSearchParams(params);
    next.set("page", String(value));
    setParams(next, { state: location.state });
  }
  const tab = ["cases", "scores", "snapshot"].includes(
    params.get("section") || "",
  )
    ? params.get("section")!
    : "cases";
  const search = params.get("q") || "";
  function update(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: key === "q", state: location.state });
  }
  const setTab = (value: string) => update("section", value);
  const setSearch = (value: string) => update("q", value);
  const listQuery =
    typeof location.state?.experimentList === "string"
      ? location.state.experimentList
      : "";
  const reviewState = {
    ...location.state,
    experimentSearch: params.toString(),
  };
  const [createOpen, setCreateOpen] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const experiment = useQuery({
    queryKey: ["experiment", id],
    queryFn: ({ signal }) =>
      api!.request<Experiment>(`/v1/experiments/${id}`, { signal }),
    enabled: !!api,
    refetchInterval: 10000,
  });
  const summary = useQuery({
    queryKey: ["summary", id],
    queryFn: ({ signal }) =>
      api!.request<Summary>(`/v1/experiments/${id}/results`, { signal }),
    enabled: !!api,
    refetchInterval: 10000,
  });
  const runs = useQuery({
    queryKey: ["case-runs", id, page],
    queryFn: ({ signal }) =>
      api!.request<{ items: CaseRun[] }>(
        `/v1/experiments/${id}/case-runs?limit=51&offset=${page * 50}`,
        { signal },
      ),
    enabled: !!api,
    refetchInterval: 10000,
  });
  const data = experiment.data;
  const visible =
    runs.data?.items
      .slice(0, 50)
      .filter((r) =>
        `${r.case.case_id} ${r.case.content.tags.join(" ")}`
          .toLowerCase()
          .includes(search.toLowerCase()),
      ) || [];
  const active =
    data && ["queued", "running", "cancel_requested"].includes(data.status);
  async function cancel() {
    if (!api) return;
    setBusy(true);
    setError(null);
    try {
      await api.post(`/v1/experiments/${id}/cancel`);
      setCancelOpen(false);
      await client.invalidateQueries();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Link
        className="back-link"
        to={listQuery ? `/experiments?${listQuery}` : "/experiments"}
      >
        <ArrowLeft size={15} />
        全部实验
      </Link>
      <PageHeading
        eyebrow={`EXPERIMENT / ${shortId(id).toUpperCase()}`}
        title={data?.snapshot.target.content.name || "实验详情"}
        description={
          data
            ? `${data.snapshot.target.content.external_version || "外部版本未知"} · 创建于 ${formatDate(data.created_at)} · 每 10 秒更新`
            : "查看用例、评分与每次执行尝试。"
        }
        action={
          data && (
            <>
              <button className="button" onClick={() => setCreateOpen(true)}>
                <GitBranch size={16} />
                关联重跑
              </button>
              {active && (
                <button
                  className="button danger"
                  onClick={() => setCancelOpen(true)}
                  disabled={data.status === "cancel_requested"}
                >
                  <Square size={14} />
                  {data.status === "cancel_requested"
                    ? "等待停止确认"
                    : "请求取消"}
                </button>
              )}
            </>
          )
        }
      />
      {!api ? (
        <section className="panel">
          <Disconnected />
        </section>
      ) : experiment.isPending ? (
        <Loading />
      ) : experiment.error ? (
        <ErrorNotice
          error={experiment.error}
          retry={() => void experiment.refetch()}
        />
      ) : (
        data && (
          <>
            <div className="experiment-strip">
              <Badge status={data.status} />
              <span>
                <Timer size={14} />
                {data.snapshot.request.timeout_seconds}s 超时
              </span>
              <span>
                {data.snapshot.request.concurrency} 并发 /{" "}
                {data.snapshot.request.repetitions} 次重复
              </span>
              <Link to={`/comparison?baseline=${id}`} className="text-button">
                选择为对比基线
                <ArrowUpRight size={14} />
              </Link>
            </div>
            {summary.error && (
              <ErrorNotice
                error={summary.error}
                retry={() => void summary.refetch()}
              />
            )}
            <Metrics
              items={[
                {
                  label: "计划用例运行",
                  value: summary.data?.planned_runs ?? "—",
                  note: "包含每个用例的重复次数",
                },
                {
                  label: "执行成功率",
                  value: formatRatio(summary.data?.execution_success_rate),
                  note: summary.data
                    ? `${summary.data.execution_successes} / ${summary.data.planned_runs} 个计划运行`
                    : "读取结果汇总",
                  accent: true,
                },
                {
                  label: "执行尝试",
                  value: summary.data?.execution_attempts ?? "—",
                  note: summary.data
                    ? `${summary.data.failed_attempts} 次失败尝试`
                    : "读取执行记录",
                },
                {
                  label: "未知尝试",
                  value: summary.data?.unknown_attempts ?? "—",
                  note: "实际结果尚待核对",
                },
              ]}
            />
            <section className="panel">
              <div className="panel-toolbar">
                <div className="tabs">
                  {[
                    { id: "cases", label: "用例执行" },
                    { id: "scores", label: "评分汇总" },
                    { id: "snapshot", label: "固定快照" },
                  ].map((t) => (
                    <button
                      key={t.id}
                      aria-pressed={tab === t.id}
                      className={tab === t.id ? "selected" : ""}
                      onClick={() => setTab(t.id)}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
                {tab === "cases" && (
                  <div className="search">
                    <Search size={15} />
                    <input
                      aria-label="搜索当前页用例"
                      placeholder="搜索当前页用例…"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                    />
                  </div>
                )}
              </div>
              {tab === "cases" ? (
                runs.isPending ? (
                  <TableLoading label="正在读取用例" />
                ) : runs.error ? (
                  <ErrorNotice
                    error={runs.error}
                    retry={() => void runs.refetch()}
                  />
                ) : !visible.length ? (
                  <Empty
                    compact
                    title={search ? "没有匹配的用例" : "暂无用例执行"}
                    description={
                      search
                        ? "调整搜索词，或翻页查看其他用例。"
                        : "用例记录将在实验创建后由后端提供。"
                    }
                  />
                ) : (
                  <>
                    <div
                      className="table-scroll"
                      role="region"
                      aria-label="用例记录，可横向滚动"
                      tabIndex={0}
                    >
                      <table>
                        <thead>
                          <tr>
                            <th>用例</th>
                            <th>执行状态</th>
                            <th>评分记录</th>
                            <th>证据 / 清理</th>
                            <th>尝试次数</th>
                            <th>
                              <span className="sr-only">查看证据</span>
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {visible.map((run) => {
                            const latest = run.attempts.at(-1);
                            return (
                              <tr key={run.id}>
                                <td>
                                  <Link
                                    className="table-title text-button"
                                    to={`/experiments/${id}/cases/${run.id}?page=${page}`}
                                    state={reviewState}
                                  >
                                    {run.case.case_id}
                                    <ArrowUpRight size={14} />
                                  </Link>
                                  <small>
                                    第 {run.repetition + 1} 次重复 ·{" "}
                                    {run.case.content.tags.join(" / ") ||
                                      "无标签"}
                                  </small>
                                </td>
                                <td>
                                  <Badge
                                    status={latest?.status || run.status}
                                  />
                                </td>
                                <td>
                                  {latest?.score_runs?.length ? (
                                    latest.score_runs.map((s) => (
                                      <div className="score-cell" key={s.id}>
                                        <Badge
                                          status={s.result?.verdict || s.status}
                                        />
                                        {s.result?.value != null && (
                                          <span className="mono">
                                            {s.result.value}
                                          </span>
                                        )}
                                      </div>
                                    ))
                                  ) : (
                                    <span className="muted">尚无评分</span>
                                  )}
                                </td>
                                <td>
                                  {latest ? (
                                    <>
                                      <Badge status={latest.evidence_status} />
                                      <small>
                                        清理：
                                        <Badge status={latest.cleanup_status} />
                                      </small>
                                    </>
                                  ) : (
                                    <span className="muted">未开始采集</span>
                                  )}
                                </td>
                                <td className="mono">{run.attempts.length}</td>
                                <td>
                                  <Link
                                    className="icon-button"
                                    to={`/experiments/${id}/cases/${run.id}?page=${page}`}
                                    state={reviewState}
                                    aria-label={`查看 ${run.case.case_id} 执行证据`}
                                  >
                                    <ListTree size={17} />
                                  </Link>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                    <Pagination
                      page={page}
                      next={runs.data!.items.length > 50}
                      onPage={setPage}
                    />
                  </>
                )
              ) : tab === "scores" ? (
                <div className="panel-content">
                  {summary.isPending ? (
                    <Loading />
                  ) : (
                    summary.data?.scorers.map((s) => (
                      <div className="scorer-summary" key={s.scorer_version_id}>
                        <div>
                          <h3>
                            {data.snapshot.scorers.find(
                              (v) => v.id === s.scorer_version_id,
                            )?.content.name || shortId(s.scorer_version_id)}
                          </h3>
                          <span className="mono muted">
                            {shortId(s.scorer_version_id)}
                          </span>
                        </div>
                        <div>
                          <span>评分覆盖率</span>
                          <strong>{formatRatio(s.score_coverage)}</strong>
                          <small>
                            {s.valid_scores} / {s.planned_runs} 计划运行
                          </small>
                        </div>
                        <div>
                          <span>有效评分通过率</span>
                          <strong>
                            {formatRatio(s.valid_score_pass_rate)}
                          </strong>
                          <small>
                            {s.passed} / {s.valid_scores} 有效评分
                          </small>
                        </div>
                        <div>
                          <span>未解决 / 不适用</span>
                          <strong>
                            {s.unresolved} / {s.not_applicable}
                          </strong>
                          <small>缺失不会按通过处理</small>
                        </div>
                      </div>
                    ))
                  )}
                  <div className="notice">
                    <p>
                      汇总由后端提供，使用首个成功尝试及其最早评分记录。重新评分保留历史，不会自动替换此汇总。
                    </p>
                  </div>
                </div>
              ) : (
                <div className="panel-content">
                  <JsonBlock
                    title="实验创建时冻结的完整配置"
                    value={data.snapshot}
                  />
                </div>
              )}
            </section>
            <p className="detail-footnote">
              实验已完成表示调度结束；执行成功、证据完整、评分通过分别判断。
            </p>
          </>
        )
      )}
      {createOpen && data && (
        <CreateExperiment source={data} onClose={() => setCreateOpen(false)} />
      )}
      {cancelOpen && (
        <Dialog
          title="请求取消实验"
          subtitle="排队工作会取消；活动执行需要 Runner 确认目标停止。"
          onClose={() => setCancelOpen(false)}
        >
          <div className="form">
            <div className="notice">
              <p>
                未确认停止的执行保留“等待停止确认”或“结果未知”，历史尝试与证据仍可查看。
              </p>
            </div>
            {error != null && <ErrorNotice error={error} />}
            <div className="form-actions">
              <button className="button" onClick={() => setCancelOpen(false)}>
                继续运行
              </button>
              <button
                className="button danger"
                disabled={busy}
                onClick={() => void cancel()}
              >
                {busy ? "正在请求…" : "确认请求取消"}
              </button>
            </div>
          </div>
        </Dialog>
      )}
    </>
  );
}
