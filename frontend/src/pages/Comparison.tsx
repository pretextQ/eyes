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
  JsonBlock,
  PageHeading,
} from "../components/ui";
import type { CaseRun, Experiment, Summary } from "../types";

export function ComparisonPage() {
  const { api } = useConnection();
  const [params, setParams] = useSearchParams();
  const baseline = params.get("baseline") || "";
  const candidate = params.get("candidate") || "";
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
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
  const allKeys = [...new Set([...aMap.keys(), ...bMap.keys()])];
  const keys = allKeys
    .filter((k) => {
      const left = aMap.get(k),
        right = bMap.get(k);
      const matches = k.toLowerCase().includes(search.toLowerCase());
      return (
        matches &&
        (filter === "all" ||
          (filter === "content"
            ? !!left && !!right && left.case.digest !== right.case.digest
            : filter === "missing"
              ? !left || !right
              : !!left &&
                !!right &&
                (left.attempts.at(-1)?.status || left.status) !==
                  (right.attempts.at(-1)?.status || right.status)))
      );
    })
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
        ) : experiments.data.length < 2 ? (
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
      {api && (
        <div className="notice comparison-notice">
          <GitCompareArrows size={17} />
          <p>
            当前提供结果并列核对，不生成回归报告或 CI
            门槛。按用例标识与重复序号排列；内容、评分口径、环境或采集能力不同时，需要单独核对可比性。
          </p>
        </div>
      )}
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
      {!api ? null : !ready ? (
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
            <ConfigurationReview left={a.data} right={b.data} />
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
              <div className="comparison-filters" aria-label="筛选原始记录差异">
                {[
                  { id: "all", label: "全部记录" },
                  { id: "content", label: "用例内容不同" },
                  { id: "status", label: "执行状态不同" },
                  { id: "missing", label: "仅单侧存在" },
                ].map((item) => (
                  <button
                    key={item.id}
                    aria-pressed={filter === item.id}
                    className={filter === item.id ? "selected" : ""}
                    onClick={() => {
                      setFilter(item.id);
                      setPage(0);
                    }}
                  >
                    {item.label}
                  </button>
                ))}
                <span>
                  {keys.length} / {allKeys.length} 条
                </span>
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
                  description="调整搜索词或差异筛选，查看其他原始记录。"
                  action={
                    <button
                      className="button"
                      onClick={() => {
                        setSearch("");
                        setFilter("all");
                        setPage(0);
                      }}
                    >
                      清除筛选
                    </button>
                  }
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
                              {!left || !right ? (
                                <span className="record-difference">
                                  仅{left ? "基线" : "候选"}存在
                                </span>
                              ) : left.case.digest !== right.case.digest ? (
                                <span className="record-difference">
                                  用例内容不同
                                </span>
                              ) : null}
                              <small className="mono">
                                A: {left?.case.digest.slice(0, 10) || "不存在"}
                                <br />
                                B: {right?.case.digest.slice(0, 10) || "不存在"}
                              </small>
                            </td>
                            <td>
                              <ComparisonCase
                                run={left}
                                id={baseline}
                                page={
                                  left
                                    ? Math.floor(ar.data!.indexOf(left) / 50)
                                    : 0
                                }
                              />
                            </td>
                            <td>
                              <ComparisonCase
                                run={right}
                                id={candidate}
                                page={
                                  right
                                    ? Math.floor(br.data!.indexOf(right) / 50)
                                    : 0
                                }
                              />
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
function ComparisonCase({
  run,
  id,
  page,
}: {
  run?: CaseRun;
  id: string;
  page: number;
}) {
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
      {latest?.result?.output != null && (
        <details className="comparison-output">
          <summary>查看最新尝试输出</summary>
          <JsonBlock
            title={`${run.case.case_id} / 最新输出`}
            value={latest.result.output}
          />
        </details>
      )}
      <Link
        className="text-button"
        to={`/experiments/${id}/cases/${run.id}?page=${page}`}
      >
        审阅执行证据
        <ArrowUpRight size={13} />
      </Link>
    </div>
  );
}

function ConfigurationReview({
  left,
  right,
}: {
  left: Experiment;
  right: Experiment;
}) {
  const rows = [
    {
      label: "测试集摘要",
      a: left.snapshot.dataset_digest,
      b: right.snapshot.dataset_digest,
    },
    {
      label: "评分口径摘要",
      a: left.snapshot.scorers
        .map((s) => s.digest)
        .sort()
        .join(" / "),
      b: right.snapshot.scorers
        .map((s) => s.digest)
        .sort()
        .join(" / "),
    },
    {
      label: "观测能力声明",
      a: left.snapshot.target.content.capabilities.observation
        .slice()
        .sort()
        .join(" / "),
      b: right.snapshot.target.content.capabilities.observation
        .slice()
        .sort()
        .join(" / "),
    },
    {
      label: "重复 / 并发 / 超时",
      a: `${left.snapshot.request.repetitions} / ${left.snapshot.request.concurrency} / ${left.snapshot.request.timeout_seconds}s`,
      b: `${right.snapshot.request.repetitions} / ${right.snapshot.request.concurrency} / ${right.snapshot.request.timeout_seconds}s`,
    },
  ];
  const differences = rows.filter((row) => row.a !== row.b).length;
  return (
    <section
      className="configuration-review"
      aria-labelledby="configuration-title"
    >
      <div className="configuration-heading">
        <div>
          <span className="section-label">BEFORE YOU COMPARE</span>
          <h2 id="configuration-title">先核对条件，再审阅变化。</h2>
        </div>
        <span
          className={`configuration-status ${differences ? "changed" : ""}`}
        >
          {differences ? `${differences} 项配置不同` : "已列配置一致"}
        </span>
      </div>
      <div className="configuration-column-labels" aria-hidden="true">
        <span>核对项</span>
        <span>A / 基线</span>
        <span>B / 待审阅</span>
        <span>状态</span>
      </div>
      <div className="configuration-rows">
        {rows.map((row) => (
          <div key={row.label}>
            <span>{row.label}</span>
            <code
              title={row.a}
              aria-label={`A / 基线 ${row.label}: ${row.a || "未提供"}`}
            >
              {row.a || "未提供"}
            </code>
            <code
              title={row.b}
              aria-label={`B / 待审阅 ${row.label}: ${row.b || "未提供"}`}
            >
              {row.b || "未提供"}
            </code>
            <span
              className={row.a === row.b ? "config-same" : "config-changed"}
            >
              {row.a === row.b ? "一致" : "不同"}
            </span>
          </div>
        ))}
      </div>
      <details className="configuration-full">
        <summary>查看完整配置摘要</summary>
        <JsonBlock
          title="A / 基线配置摘要"
          value={Object.fromEntries(rows.map((row) => [row.label, row.a]))}
        />
        <JsonBlock
          title="B / 待审阅配置摘要"
          value={Object.fromEntries(rows.map((row) => [row.label, row.b]))}
        />
      </details>
      <p>
        这里只核对已记录的配置；外部环境、实际采集覆盖和服务端尝试选择仍需确认。逐用例展示最新尝试，汇总采用后端选择口径。
      </p>
    </section>
  );
}
