import { formatDate, formatRatio, shortId } from "../format";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowUpRight,
  Check,
  Copy,
  Download,
  FileBox,
  GitBranch,
  ListTree,
  RefreshCw,
  Search,
  Square,
  Timer,
} from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { useConnection } from "../connection";
import {
  Badge,
  CheckItem,
  Dialog,
  Disconnected,
  Empty,
  ErrorNotice,
  Field,
  JsonBlock,
  Loading,
  Metrics,
  PageHeading,
  Pagination,
} from "../components/ui";
import type {
  Attempt,
  CaseRun,
  Event,
  Experiment,
  Manifest,
  Summary,
} from "../types";
import { CreateExperiment } from "./Experiments";

export function ExperimentPage() {
  const { id } = useParams();
  return <ExperimentView key={id} id={id!} />;
}
function ExperimentView({ id }: { id: string }) {
  const { api } = useConnection();
  const client = useQueryClient();
  const [tab, setTab] = useState("cases");
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<CaseRun | null>(null);
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
  const selectedFresh =
    runs.data?.items.find((r) => r.id === selected?.id) || selected;
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
      <Link className="back-link" to="/experiments">
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
                  <Loading />
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
                    <div className="table-scroll">
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
                                  <button
                                    className="table-title text-button"
                                    onClick={() => setSelected(run)}
                                  >
                                    {run.case.case_id}
                                    <ArrowUpRight size={14} />
                                  </button>
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
                                  <button
                                    className="icon-button"
                                    onClick={() => setSelected(run)}
                                    aria-label={`查看 ${run.case.case_id} 执行证据`}
                                  >
                                    <ListTree size={17} />
                                  </button>
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
      {selectedFresh && data && (
        <AttemptDialog
          key={selectedFresh.id}
          run={selectedFresh}
          experiment={data}
          onClose={() => setSelected(null)}
        />
      )}
    </>
  );
}
function AttemptDialog({
  run,
  experiment,
  onClose,
}: {
  run: CaseRun;
  experiment: Experiment;
  onClose: () => void;
}) {
  const { api } = useConnection();
  const client = useQueryClient();
  const [selectedAttemptId, setAttemptId] = useState(
    run.attempts.at(-1)?.id || "",
  );
  const attemptId = run.attempts.some((a) => a.id === selectedAttemptId)
    ? selectedAttemptId
    : run.attempts.at(-1)?.id || "";
  const [tab, setTab] = useState("result");
  const [eventPage, setEventPage] = useState(0);
  const [manifestPage, setManifestPage] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [message, setMessage] = useState("");
  const [resolveOpen, setResolveOpen] = useState(false);
  const attempt = useQuery({
    queryKey: ["attempt", attemptId],
    queryFn: ({ signal }) =>
      api!.request<Attempt>(`/v1/attempts/${attemptId}`, { signal }),
    enabled: !!api && !!attemptId,
    refetchInterval: 10000,
  });
  const events = useQuery({
    queryKey: ["events", attemptId, eventPage],
    queryFn: ({ signal }) =>
      api!.request<{ items: Event[] }>(
        `/v1/attempts/${attemptId}/events?limit=51&offset=${eventPage * 50}`,
        { signal },
      ),
    enabled: !!api && !!attemptId && tab === "events",
    refetchInterval: 10000,
  });
  const manifests = useQuery({
    queryKey: ["manifests", attemptId, manifestPage],
    queryFn: ({ signal }) =>
      api!.request<{ items: Manifest[] }>(
        `/v1/attempts/${attemptId}/manifests?limit=51&offset=${manifestPage * 50}`,
        { signal },
      ),
    enabled: !!api && !!attemptId && tab === "evidence",
    refetchInterval: 10000,
  });
  const inline = run.attempts.find((a) => a.id === attemptId);
  const current = attempt.data || inline;
  async function rescore() {
    if (!api) return;
    setBusy(true);
    setError(null);
    setMessage("");
    try {
      await api.post(`/v1/attempts/${attemptId}/rescore`);
      setMessage("已创建新的评分记录，保留原评分历史。");
      await client.invalidateQueries();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  async function copy() {
    try {
      await navigator.clipboard.writeText(current!.trace_id);
      setMessage("Trace ID 已复制。");
    } catch {
      setError(new Error("无法写入剪贴板，请手动复制 Trace ID。"));
    }
  }
  async function download(id: string) {
    setBusy(true);
    setError(null);
    try {
      await api!.download(id);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      wide
      title={run.case.case_id}
      subtitle={`第 ${run.repetition + 1} 次重复 · ${run.attempts.length} 次执行尝试`}
      onClose={onClose}
    >
      <div className="attempt-content">
        {run.attempts.length > 0 && (
          <div className="attempt-selector">
            <Field label="执行尝试">
              <select
                value={attemptId}
                onChange={(e) => {
                  setAttemptId(e.target.value);
                  setEventPage(0);
                  setManifestPage(0);
                  setError(null);
                  setMessage("");
                }}
              >
                {run.attempts.map((a, i) => (
                  <option key={a.id} value={a.id}>
                    尝试 {i + 1} · {a.status} · {shortId(a.id)}
                  </option>
                ))}
              </select>
            </Field>
            {current?.trace_id && (
              <button className="button small" onClick={() => void copy()}>
                <Copy size={14} />
                Trace ID
              </button>
            )}
          </div>
        )}
        {attempt.error && (
          <ErrorNotice
            error={attempt.error}
            retry={() => void attempt.refetch()}
          />
        )}
        {current && (
          <div className="attempt-status">
            <span>
              执行 <Badge status={current.status} />
            </span>
            <span>
              证据 <Badge status={current.evidence_status} />
            </span>
            <span>
              清理 <Badge status={current.cleanup_status} />
            </span>
          </div>
        )}
        <div className="tabs attempt-tabs">
          {[
            { id: "result", label: "输入 / 输出" },
            { id: "events", label: "执行事件" },
            { id: "scores", label: "评分历史" },
            { id: "evidence", label: "证据清单" },
          ].map((t) => (
            <button
              key={t.id}
              className={tab === t.id ? "selected" : ""}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
        {tab === "result" ? (
          <div className="attempt-body">
            <JsonBlock title="用例输入" value={run.case.content.input} />
            <JsonBlock title="预期" value={run.case.content.expectations} />
            {current ? (
              <>
                <JsonBlock
                  title="执行结果（包括输出、异常与采集说明）"
                  value={current.result}
                />
                <div className="key-values">
                  <div>
                    <span>Trace ID</span>
                    <code>{current.trace_id}</code>
                  </div>
                  <div>
                    <span>执行结束</span>
                    <span>{formatDate(current.finished_at)}</span>
                  </div>
                </div>
                {current.resolutions?.length ? (
                  <JsonBlock title="状态核对历史" value={current.resolutions} />
                ) : null}
              </>
            ) : (
              <Empty
                compact
                title="尚无执行尝试"
                description="用例排队中，或已在执行前取消。"
              />
            )}
          </div>
        ) : tab === "events" ? (
          !attemptId ? (
            <Empty
              compact
              title="暂无执行事件"
              description="目标尚未开始执行。"
            />
          ) : events.isPending ? (
            <Loading />
          ) : events.error ? (
            <ErrorNotice
              error={events.error}
              retry={() => void events.refetch()}
            />
          ) : (
            <div className="attempt-body">
              <div className="notice">
                <ListTree size={17} />
                <p>
                  按服务端接收顺序展示。发生时间、生产者序号和父 Span
                  单独保留；不同生产者不构成全局执行顺序。观测范围：
                  {experiment.snapshot.target.content.capabilities.observation.join(
                    " / ",
                  )}
                  。
                </p>
              </div>
              {!events.data.items.length ? (
                <Empty
                  compact
                  title="没有已采集事件"
                  description="无事件不表示没有内部执行；采集范围取决于目标接入。"
                />
              ) : (
                <div className="timeline">
                  {events.data.items.slice(0, 50).map((event) => (
                    <details key={event.id} className="event-item">
                      <summary>
                        <span className="timeline-point" />
                        <div>
                          <strong>{event.content.type}</strong>
                          <small>
                            {event.content.source} · {event.producer_id} · 序号{" "}
                            {event.content.sequence}
                          </small>
                        </div>
                        <time>{formatDate(event.content.occurred_at)}</time>
                      </summary>
                      <div className="event-detail">
                        <div className="key-values">
                          <div>
                            <span>Span / Parent</span>
                            <code>
                              {event.content.span_id} /{" "}
                              {event.content.parent_span_id || "根节点"}
                            </code>
                          </div>
                          <div>
                            <span>接收时间</span>
                            <span>{formatDate(event.created_at)}</span>
                          </div>
                          <div>
                            <span>证据引用</span>
                            <code>event:{event.id}</code>
                          </div>
                        </div>
                        <JsonBlock value={event.content.data} />
                      </div>
                    </details>
                  ))}
                </div>
              )}
              <Pagination
                page={eventPage}
                next={events.data.items.length > 50}
                onPage={setEventPage}
              />
            </div>
          )
        ) : tab === "scores" ? (
          <div className="attempt-body">
            {!inline?.score_runs?.length ? (
              <Empty
                compact
                title="尚无评分记录"
                description="执行或证据准备完成后，后端会安排评分。"
              />
            ) : (
              inline.score_runs.map((score) => (
                <div className="score-detail" key={score.id}>
                  <div className="score-detail-heading">
                    <div>
                      <strong>
                        {experiment.snapshot.scorers.find(
                          (s) => s.id === score.scorer_id,
                        )?.content.name || shortId(score.scorer_id)}
                      </strong>
                      <small className="mono">
                        ScoreRun {shortId(score.id)} ·{" "}
                        {formatDate(score.created_at)}
                      </small>
                    </div>
                    <Badge status={score.result?.verdict || score.status} />
                    {score.result?.value != null && (
                      <strong className="numeric-score">
                        {score.result.value}
                      </strong>
                    )}
                  </div>
                  <p>{score.result?.reason || "评分尚未返回结果。"}</p>
                  <div className="key-values">
                    <div>
                      <span>运行状态</span>
                      <Badge status={score.status} />
                    </div>
                    <div>
                      <span>固定清单</span>
                      <code>{score.manifest_id}</code>
                    </div>
                  </div>
                  {score.result?.evidence_refs.length ? (
                    <details>
                      <summary>
                        评分证据引用 · {score.result.evidence_refs.length}
                      </summary>
                      <ul className="reference-list">
                        {score.result.evidence_refs.map((ref) => (
                          <li key={ref}>
                            <code>{ref}</code>
                          </li>
                        ))}
                      </ul>
                    </details>
                  ) : null}
                </div>
              ))
            )}
          </div>
        ) : !attemptId ? (
          <Empty
            compact
            title="暂无证据清单"
            description="没有执行尝试可以查询。"
          />
        ) : manifests.isPending ? (
          <Loading />
        ) : manifests.error ? (
          <ErrorNotice
            error={manifests.error}
            retry={() => void manifests.refetch()}
          />
        ) : (
          <div className="attempt-body">
            <div className="notice">
              <FileBox size={17} />
              <p>
                封存仅表示声明采集范围完成；晚到证据形成新的清单版本。未报告的事件丢弃数保持未知。
              </p>
            </div>
            {!manifests.data.items.length ? (
              <Empty
                compact
                title="证据还未封存"
                description="执行结束后可查看固定清单；评分将绑定具体清单版本。"
              />
            ) : (
              manifests.data.items.slice(0, 50).map((m) => (
                <div className="manifest" key={m.id}>
                  <div className="manifest-heading">
                    <strong>清单 v{m.version}</strong>
                    <Badge status={m.content.status} />
                    <span className="mono">{shortId(m.id)}</span>
                  </div>
                  <div className="manifest-counts">
                    <span>{m.content.event_ids.length} 个事件</span>
                    <span>{m.content.artifact_ids.length} 个产物</span>
                    <span>丢弃事件：{m.content.dropped_events ?? "未知"}</span>
                  </div>
                  {m.content.artifact_ids.map((artifact) => (
                    <button
                      disabled={busy}
                      className="artifact-link"
                      key={artifact}
                      onClick={() => void download(artifact)}
                    >
                      <Download size={15} />
                      <span className="mono">{artifact}</span>
                    </button>
                  ))}
                  <details>
                    <summary>查看完整清单和冻结结果</summary>
                    <JsonBlock value={m.content} />
                  </details>
                </div>
              ))
            )}
            <Pagination
              page={manifestPage}
              next={manifests.data.items.length > 50}
              onPage={setManifestPage}
            />
          </div>
        )}
        {error != null && <ErrorNotice error={error} />}{" "}
        {message && (
          <div className="notice success" role="status">
            <Check size={17} />
            {message}
          </div>
        )}
        <div className="form-actions">
          {current?.status === "unknown" && (
            <button
              className="button danger"
              onClick={() => setResolveOpen(true)}
            >
              核对未知状态
            </button>
          )}
          {current?.finished_at && (
            <button
              className="button"
              disabled={busy}
              onClick={() => void rescore()}
            >
              <RefreshCw size={15} />
              {busy ? "正在提交…" : "创建重新评分"}
            </button>
          )}
          <button className="button" onClick={onClose}>
            关闭
          </button>
        </div>
      </div>
      {resolveOpen && current && (
        <ResolveDialog id={current.id} onClose={() => setResolveOpen(false)} />
      )}
    </Dialog>
  );
}
function ResolveDialog({ id, onClose }: { id: string; onClose: () => void }) {
  const { api } = useConnection();
  const client = useQueryClient();
  const [status, setStatus] = useState("failed");
  const [reason, setReason] = useState("");
  const [output, setOutput] = useState("{}");
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  async function submit(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const parsed = status === "succeeded" ? JSON.parse(output) : null;
      if (
        parsed !== null &&
        (typeof parsed !== "object" || Array.isArray(parsed))
      )
        throw new Error("成功输出必须为 JSON 对象。");
      await api!.post(`/v1/attempts/${id}/resolve`, {
        status,
        reason: reason.trim(),
        stopped_confirmed: true,
        output: parsed,
      });
      await client.invalidateQueries();
      onClose();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      title="核对未知执行状态"
      subtitle="只有确认目标已停止，才能释放对应额度。"
      onClose={onClose}
    >
      <form className="form" onSubmit={submit}>
        <Field label="实际结果">
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="failed">执行失败</option>
            <option value="succeeded">执行成功</option>
            <option value="cancelled">已取消</option>
            <option value="timed_out">已超时</option>
          </select>
        </Field>
        <Field label="核对依据与原因">
          <textarea
            required
            minLength={1}
            maxLength={2000}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="记录核对来源、已确认状态和停止依据"
          />
        </Field>
        {status === "succeeded" && (
          <Field label="确认的输出 / JSON">
            <textarea
              className="code-input"
              required
              value={output}
              onChange={(e) => setOutput(e.target.value)}
            />
          </Field>
        )}
        <CheckItem checked={confirmed} onChange={setConfirmed}>
          我已确认目标执行停止
        </CheckItem>
        {error != null && <ErrorNotice error={error} />}
        <div className="form-actions">
          <button type="button" className="button" onClick={onClose}>
            取消
          </button>
          <button
            className="button primary"
            disabled={busy || !confirmed || !reason.trim()}
          >
            {busy ? "正在提交…" : "追加核对记录"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
