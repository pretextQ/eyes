import { formatDate, shortId } from "../format";
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowUpRight,
  Check,
  Copy,
  Download,
  FileBox,
  ListTree,
  RefreshCw,
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
  CheckItem,
  Dialog,
  Disconnected,
  Empty,
  ErrorNotice,
  Field,
  JsonBlock,
  Loading,
  PageHeading,
  Pagination,
} from "../components/ui";
import { EventExplorer } from "../components/EventExplorer";
import type { Attempt, CaseRun, Event, Experiment, Manifest } from "../types";

function pageNumber(value: string | null) {
  const number = Number(value);
  return Number.isSafeInteger(number) && number >= 0 ? number : 0;
}

export function CaseWorkspacePage() {
  const { id, runId } = useParams();
  return <CaseWorkspace key={id} id={id!} runId={runId!} />;
}
function CaseWorkspace({ id, runId }: { id: string; runId: string }) {
  const { api } = useConnection();
  const location = useLocation();
  const [params] = useSearchParams();
  const page = pageNumber(params.get("page"));
  const experiment = useQuery({
    queryKey: ["experiment", id],
    queryFn: ({ signal }) =>
      api!.request<Experiment>(`/v1/experiments/${id}`, { signal }),
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
  const run = runs.data?.items.slice(0, 50).find((run) => run.id === runId);
  const experimentSearch =
    typeof location.state?.experimentSearch === "string"
      ? location.state.experimentSearch
      : `page=${page}`;
  const back = `/experiments/${id}?${experimentSearch}`;
  return (
    <>
      <Link className="back-link" to={back} state={location.state}>
        <ArrowLeft size={15} />
        返回实验 · {shortId(id)}
      </Link>
      <PageHeading
        eyebrow="EVIDENCE / REVIEW"
        title="执行审阅"
        description={
          experiment.data
            ? `${experiment.data.snapshot.target.content.name} · ${experiment.data.snapshot.target.content.external_version || "外部版本未知"}`
            : "从用例结果追溯执行过程与评分依据。"
        }
      />
      {!api ? (
        <section className="panel">
          <Disconnected />
        </section>
      ) : experiment.isPending || runs.isPending ? (
        <Loading label="正在读取执行记录" />
      ) : experiment.error || runs.error ? (
        <ErrorNotice
          error={experiment.error || runs.error}
          retry={() => {
            void experiment.refetch();
            void runs.refetch();
          }}
        />
      ) : !run || !experiment.data ? (
        <Empty
          title="本页没有该用例记录"
          description="返回实验选择用例；分页位置随审阅链接保存。"
          action={
            <Link className="button primary" to={back} state={location.state}>
              返回实验
            </Link>
          }
        />
      ) : (
        <div className="review-layout">
          <aside className="case-index" aria-label="本页用例导航">
            <div className="case-index-heading">
              <span className="section-label">本页用例</span>
              <span className="count">
                {runs.data!.items.slice(0, 50).length}
              </span>
            </div>
            <nav>
              {runs.data!.items.slice(0, 50).map((item) => (
                <Link
                  key={item.id}
                  to={`/experiments/${id}/cases/${item.id}?page=${page}`}
                  state={location.state}
                  aria-current={item.id === runId ? "page" : undefined}
                  className={item.id === runId ? "selected" : ""}
                >
                  <strong>{item.case.case_id}</strong>
                  <small>
                    重复 {item.repetition + 1} · {item.attempts.length} 次尝试
                  </small>
                  <Badge status={item.attempts.at(-1)?.status || item.status} />
                </Link>
              ))}
            </nav>
            <Link
              className="text-button case-index-back"
              to={back}
              state={location.state}
            >
              返回用例列表
              <ArrowUpRight size={14} />
            </Link>
          </aside>
          <AttemptReview key={run.id} run={run} experiment={experiment.data} />
        </div>
      )}
    </>
  );
}

function AttemptReview({
  run,
  experiment,
}: {
  run: CaseRun;
  experiment: Experiment;
}) {
  const { api } = useConnection();
  const client = useQueryClient();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const selectedAttemptId = params.get("attempt") || "";
  const attemptId = run.attempts.some((a) => a.id === selectedAttemptId)
    ? selectedAttemptId
    : run.attempts.at(-1)?.id || "";
  const tab = ["result", "events", "scores", "evidence"].includes(
    params.get("view") || "",
  )
    ? params.get("view")!
    : "events";
  const eventPage = pageNumber(params.get("events"));
  const manifestPage = pageNumber(params.get("manifests"));
  function update(values: Record<string, string>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(values)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    setParams(next, { state: location.state });
  }
  const setTab = (value: string) => update({ view: value });
  const setEventPage = (value: number) =>
    update({ events: String(value), event: "" });
  const setManifestPage = (value: number) =>
    update({ manifests: String(value) });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [message, setMessage] = useState("");
  const [resolveOpen, setResolveOpen] = useState(false);
  const locating = useRef<AbortController | null>(null);
  useEffect(() => () => locating.current?.abort(), [attemptId]);
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
  async function locate(reference: string) {
    if (!api) return;
    setBusy(true);
    setError(null);
    setMessage("");
    try {
      const [kind, value] = reference.split(":");
      if (kind === "artifact" && value) {
        await api.download(value);
      } else if (kind === "event" && value) {
        locating.current?.abort();
        const controller = new AbortController();
        locating.current = controller;
        const signal = AbortSignal.any([
          controller.signal,
          AbortSignal.timeout(15000),
        ]);
        for (let offset = 0; ; offset += 200) {
          const batch = await api.request<{ items: Event[] }>(
            `/v1/attempts/${attemptId}/events?limit=200&offset=${offset}`,
            { signal },
          );
          const index = batch.items.findIndex((item) => item.id === value);
          if (index >= 0) {
            update({
              view: "events",
              events: String(Math.floor((offset + index) / 50)),
              event: value,
            });
            return;
          }
          if (batch.items.length < 200)
            throw new Error("引用事件当前不可读取，请检查证据保留状态。");
        }
      } else if (kind === "manifest" && value) {
        const index =
          inline?.manifests?.findIndex((item) => item.id === value) ?? -1;
        if (index < 0) throw new Error("固定清单尚未读取，请刷新用例记录。");
        update({
          view: "evidence",
          manifests: String(Math.floor(index / 50)),
          manifest: value,
        });
      } else if (reference === "result") {
        update({ view: "result" });
      } else {
        setMessage("该引用未提供可直接定位的资源类型，请核对完整证据清单。");
        update({ view: "evidence" });
      }
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError"))
        setError(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="review-content" aria-label="执行证据审阅">
      <div className="review-heading">
        <div>
          <span className="section-label">CASE / EXECUTION RECORD</span>
          <h2>{run.case.case_id}</h2>
          <p>
            第 {run.repetition + 1} 次重复 · {run.attempts.length} 次执行尝试
          </p>
        </div>
        <ListTree size={24} strokeWidth={1.2} />
      </div>
      <div className="attempt-content">
        {run.attempts.length > 0 && (
          <div className="attempt-selector">
            <Field label="执行尝试">
              <select
                value={attemptId}
                disabled={busy}
                onChange={(e) => {
                  update({
                    attempt: e.target.value,
                    events: "",
                    manifests: "",
                    event: "",
                    manifest: "",
                  });
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
              aria-pressed={tab === t.id}
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
              <EventExplorer
                key={attemptId}
                events={events.data.items.slice(0, 50)}
                selectedId={params.get("event") || ""}
                onSelect={(value) => update({ event: value })}
              />
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
                      <button
                        className="text-button"
                        onClick={() =>
                          void locate(`manifest:${score.manifest_id}`)
                        }
                      >
                        <code>{score.manifest_id}</code>
                        <ArrowUpRight size={13} />
                      </button>
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
                            <button
                              className="reference-link"
                              disabled={busy}
                              onClick={() => void locate(ref)}
                            >
                              <ArrowUpRight size={14} />
                              <code>{ref}</code>
                            </button>
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
                <div
                  className={`manifest ${params.get("manifest") === m.id ? "highlighted" : ""}`}
                  key={m.id}
                >
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
        </div>
      </div>
      {resolveOpen && current && (
        <ResolveDialog id={current.id} onClose={() => setResolveOpen(false)} />
      )}
    </section>
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
