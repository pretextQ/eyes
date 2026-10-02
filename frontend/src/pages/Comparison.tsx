import { formatDate, formatRatio, shortId } from "../format";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  ArrowUpRight,
  GitCompareArrows,
  Search,
} from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { useConnection } from "../connection";
import {
  Badge,
  Disconnected,
  Empty,
  ErrorNotice,
  Field,
  Loading,
  PageHeading,
} from "../components/ui";
import type { CaseRun, Experiment, Summary } from "../types";

export function ComparisonPage() {
  const { api } = useConnection();
  const [params, setParams] = useSearchParams();
  const baseline = params.get("baseline") || "";
  const candidate = params.get("candidate") || "";
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const experiments = useQuery({
    queryKey: ["comparison-experiments"],
    queryFn: async ({ signal }) => {
      const items: Experiment[] = [];
      for (let offset = 0; ; offset += 200) {
        const batch = await api!.request<{ items: Experiment[] }>(
          `/v1/experiments?limit=200&offset=${offset}`,
          { signal },
        );
        items.push(...batch.items);
        if (batch.items.length < 200) return items;
      }
    },
    enabled: !!api,
  });
  const a = useQuery({
    queryKey: ["experiment", baseline],
    queryFn: ({ signal }) =>
      api!.request<Experiment>(`/v1/experiments/${baseline}`, { signal }),
    enabled: !!api && !!baseline,
  });
  const b = useQuery({
    queryKey: ["experiment", candidate],
    queryFn: ({ signal }) =>
      api!.request<Experiment>(`/v1/experiments/${candidate}`, { signal }),
    enabled: !!api && !!candidate,
  });
  const ar = useQuery({
    queryKey: ["comparison-runs", baseline],
    queryFn: ({ signal }) => api!.caseRuns(baseline, signal),
    enabled: !!api && !!baseline,
  });
  const br = useQuery({
    queryKey: ["comparison-runs", candidate],
    queryFn: ({ signal }) => api!.caseRuns(candidate, signal),
    enabled: !!api && !!candidate,
  });
  const as = useQuery({
    queryKey: ["summary", baseline],
    queryFn: ({ signal }) =>
      api!.request<Summary>(`/v1/experiments/${baseline}/results`, { signal }),
    enabled: !!api && !!baseline,
  });
  const bs = useQuery({
    queryKey: ["summary", candidate],
    queryFn: ({ signal }) =>
      api!.request<Summary>(`/v1/experiments/${candidate}/results`, { signal }),
    enabled: !!api && !!candidate,
  });
  const ready = baseline && candidate && baseline !== candidate;
  const resultsReady = ar.data && br.data;
  const error =
    a.error || b.error || ar.error || br.error || as.error || bs.error;
  const aMap = new Map(
    ar.data?.map((run) => [`${run.case.case_id}::${run.repetition}`, run]),
  );
  const bMap = new Map(
    br.data?.map((run) => [`${run.case.case_id}::${run.repetition}`, run]),
  );
  const keys = [...new Set([...aMap.keys(), ...bMap.keys()])]
    .filter((k) => k.toLowerCase().includes(search.toLowerCase()))
    .sort();
  function select(which: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(which, value);
    else next.delete(which);
    if (which === "baseline" && value === candidate) next.delete("candidate");
    setParams(next);
    setPage(0);
  }
  return (
    <>
      <PageHeading
        eyebrow="02 / COMPARISON"
        title="结果对比"
        description="并列审阅两次实验的汇总与逐用例记录，核对变化的来源。"
        action={
          ready && (
            <button
              className="button"
              onClick={() => {
                const next = new URLSearchParams();
                next.set("baseline", candidate);
                next.set("candidate", baseline);
                setParams(next);
                setPage(0);
              }}
            >
              <GitCompareArrows size={16} />
              交换实验
            </button>
          )
        }
      />
      <section className="panel comparison-panel">
        {!api ? (
          <Disconnected />
        ) : experiments.isPending ? (
          <Loading />
        ) : experiments.error ? (
          <ErrorNotice
            error={experiments.error}
            retry={() => void experiments.refetch()}
          />
        ) : !experiments.data.length ? (
          <Empty
            title="先运行实验，再审阅变化"
            description="创建至少两次实验，保留各自的目标、用例和评分版本。"
            action={
              <Link className="button primary" to="/experiments">
                前往实验
                <ArrowRight size={16} />
              </Link>
            }
          />
        ) : (
          <div className="comparison-picker">
            <Field label="A / 基线实验">
              <select
                value={baseline}
                onChange={(e) => select("baseline", e.target.value)}
              >
                <option value="">选择基线实验</option>
                {experiments.data.map((exp) => (
                  <option key={exp.id} value={exp.id}>
                    {exp.snapshot.target.content.name} · {shortId(exp.id)} ·{" "}
                    {formatDate(exp.created_at)}
                  </option>
                ))}
              </select>
            </Field>
            <div className="compare-arrow">
              <ArrowRight size={20} />
            </div>
            <Field label="B / 待审阅实验">
              <select
                value={candidate}
                onChange={(e) => select("candidate", e.target.value)}
              >
                <option value="">选择另一实验</option>
                {experiments.data
                  .filter((exp) => exp.id !== baseline)
                  .map((exp) => (
                    <option key={exp.id} value={exp.id}>
                      {exp.snapshot.target.content.name} · {shortId(exp.id)} ·{" "}
                      {formatDate(exp.created_at)}
                    </option>
                  ))}
              </select>
            </Field>
          </div>
        )}
      </section>
      <div className="notice comparison-notice">
        <GitCompareArrows size={17} />
        <p>
          当前提供结果并列核对，不生成回归报告或 CI
          门槛。按用例标识与重复序号排列；内容、评分口径、环境或采集能力不同时，需要单独核对可比性。
        </p>
      </div>
      {error && (
        <ErrorNotice
          error={error}
          retry={() => {
            void a.refetch();
            void b.refetch();
            void ar.refetch();
            void br.refetch();
            void as.refetch();
            void bs.refetch();
          }}
        />
      )}
      {!api || !ready ? (
        <div className="comparison-placeholder">
          <div className="comparison-line" />
          <GitCompareArrows size={32} strokeWidth={1.2} />
          <h3>保留基线，审阅下一次迭代</h3>
          <p>选择两次实验后，查看固定配置、执行与评分结果。</p>
        </div>
      ) : a.isPending ||
        b.isPending ||
        ar.isPending ||
        br.isPending ||
        as.isPending ||
        bs.isPending ? (
        <Loading label="正在读取两组实验记录" />
      ) : (
        a.data &&
        b.data &&
        as.data &&
        bs.data && (
          <>
            <div className="comparison-summaries">
              <ComparisonSummary
                label="A / BASELINE"
                experiment={a.data}
                summary={as.data}
              />
              <ComparisonSummary
                label="B / CANDIDATE"
                experiment={b.data}
                summary={bs.data}
              />
            </div>
            <section className="panel">
              <div className="panel-toolbar">
                <div className="toolbar-title">
                  逐用例记录 <span className="count">{keys.length}</span>
                </div>
                <div className="search">
                  <Search size={15} />
                  <input
                    aria-label="搜索对比用例"
                    placeholder="搜索用例标识…"
                    value={search}
                    onChange={(e) => {
                      setSearch(e.target.value);
                      setPage(0);
                    }}
                  />
                </div>
              </div>
              {!resultsReady ? (
                <Empty
                  compact
                  title="用例记录读取不完整"
                  description="请重试失败的数据请求。"
                />
              ) : !keys.length ? (
                <Empty
                  compact
                  title="没有匹配的用例"
                  description="检查搜索词或实验是否包含用例。"
                />
              ) : (
                <div className="table-scroll">
                  <table className="comparison-table">
                    <thead>
                      <tr>
                        <th>用例 / 重复序号</th>
                        <th>A · 最新尝试记录</th>
                        <th>B · 最新尝试记录</th>
                      </tr>
                    </thead>
                    <tbody>
                      {keys.slice(page * 50, (page + 1) * 50).map((key) => {
                        const left = aMap.get(key),
                          right = bMap.get(key);
                        const run = left || right!;
                        return (
                          <tr key={key}>
                            <td>
                              <strong>{run.case.case_id}</strong>
                              <small>第 {run.repetition + 1} 次重复</small>
                              <small className="mono">
                                A: {left?.case.digest.slice(0, 10) || "不存在"}
                                <br />
                                B: {right?.case.digest.slice(0, 10) || "不存在"}
                              </small>
                            </td>
                            <td>
                              <ComparisonCase run={left} id={baseline} />
                            </td>
                            <td>
                              <ComparisonCase run={right} id={candidate} />
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
              {keys.length > 50 && (
                <div className="pagination">
                  <span>
                    第 {page + 1} 页 · 共 {keys.length} 个用例运行
                  </span>
                  <div>
                    <button
                      className="button small"
                      disabled={!page}
                      onClick={() => setPage((p) => p - 1)}
                    >
                      上一页
                    </button>
                    <button
                      className="button small"
                      disabled={(page + 1) * 50 >= keys.length}
                      onClick={() => setPage((p) => p + 1)}
                    >
                      下一页
                    </button>
                  </div>
                </div>
              )}
            </section>
          </>
        )
      )}
    </>
  );
}
function ComparisonSummary({
  label,
  experiment,
  summary,
}: {
  label: string;
  experiment: Experiment;
  summary: Summary;
}) {
  return (
    <div className="comparison-summary">
      <div className="eyebrow">{label}</div>
      <h2>
        {experiment.snapshot.target.content.name}
        <Link
          className="icon-button"
          aria-label={`打开实验 ${shortId(experiment.id)}`}
          to={`/experiments/${experiment.id}`}
        >
          <ArrowUpRight size={17} />
        </Link>
      </h2>
      <div className="summary-version">
        <span>
          {experiment.snapshot.target.content.external_version ||
            "外部版本未知"}
        </span>
        <Badge status={experiment.status} />
      </div>
      <div className="summary-rate">
        <strong>{formatRatio(summary.execution_success_rate)}</strong>
        <span>
          执行成功
          <br />
          {summary.execution_successes} / {summary.planned_runs} 计划运行
        </span>
      </div>
      <div className="key-values">
        <div>
          <span>数据集摘要</span>
          <code>{experiment.snapshot.dataset_digest.slice(0, 16)}</code>
        </div>
        <div>
          <span>重复 / 并发</span>
          <span>
            {experiment.snapshot.request.repetitions} /{" "}
            {experiment.snapshot.request.concurrency}
          </span>
        </div>
        <div>
          <span>观测范围</span>
          <span>
            {experiment.snapshot.target.content.capabilities.observation.join(
              " / ",
            )}
          </span>
        </div>
        {experiment.snapshot.scorers.map((s) => (
          <div key={s.id}>
            <span>{s.content.name}</span>
            <code>{s.digest.slice(0, 16)}</code>
          </div>
        ))}
      </div>
      {summary.scorers.map((s) => (
        <div className="comparison-score" key={s.scorer_version_id}>
          <span>
            {
              experiment.snapshot.scorers.find(
                (v) => v.id === s.scorer_version_id,
              )?.content.name
            }
          </span>
          <div>
            有效通过 {s.passed}/{s.valid_scores} · 覆盖 {s.valid_scores}/
            {s.planned_runs} · 未解决 {s.unresolved}
          </div>
        </div>
      ))}
    </div>
  );
}
function ComparisonCase({ run, id }: { run?: CaseRun; id: string }) {
  if (!run) return <span className="muted">该实验中不存在</span>;
  const latest = run.attempts.at(-1);
  return (
    <div className="comparison-case">
      <Badge status={latest?.status || run.status} />
      {latest?.score_runs?.map((s) => (
        <div className="score-cell" key={s.id}>
          <span className="mono">{shortId(s.scorer_id)}</span>
          <Badge status={s.result?.verdict || s.status} />
          {s.result?.value != null && <span>{s.result.value}</span>}
        </div>
      ))}
      <small>
        {run.attempts.length} 次尝试 · 证据{" "}
        {latest?.evidence_status || "未开始"}
      </small>
      <Link className="text-button" to={`/experiments/${id}`}>
        审阅实验
        <ArrowUpRight size={13} />
      </Link>
    </div>
  );
}
