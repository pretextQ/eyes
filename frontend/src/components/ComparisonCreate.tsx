import { useRef, useState } from "react";
import {
  useInfiniteQuery,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { GitCompareArrows } from "lucide-react";
import { Link } from "react-router-dom";
import { useConnection } from "../connection";
import { formatDate, shortId } from "../format";
import type { Experiment } from "../types";
import type {
  ComparisonReport,
  ComparisonRequest,
  GatePolicy,
} from "@/lib/comparison";
import { Empty, ErrorNotice, Loading } from "./ui";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "./ui/field";
import { Alert, AlertDescription, AlertTitle } from "./ui/alert";

const defaultGate: GatePolicy = {
  max_regressions: 0,
  min_comparable_coverage: 1,
  min_candidate_pass_rate: 1,
  min_execution_success_rate: 1,
  numeric_tolerance: 0,
};
const gateFields: {
  key: keyof GatePolicy;
  label: string;
  percent?: boolean;
  integer?: boolean;
}[] = [
  { key: "max_regressions", label: "每组允许退化用例数", integer: true },
  {
    key: "min_comparable_coverage",
    label: "最低可比覆盖率（%）",
    percent: true,
  },
  {
    key: "min_candidate_pass_rate",
    label: "候选最低通过率（%）",
    percent: true,
  },
  {
    key: "min_execution_success_rate",
    label: "候选最低执行成功率（%）",
    percent: true,
  },
  { key: "numeric_tolerance", label: "数值变化容差" },
];

export function ComparisonCreate({
  initialBaseline,
  initialCandidate,
  initialRequest,
  onCreated,
}: {
  initialBaseline: string;
  initialCandidate: string;
  initialRequest?: ComparisonRequest;
  onCreated: (id: string) => void;
}) {
  const { api } = useConnection();
  const [baseline, setBaseline] = useState(initialBaseline);
  const [candidate, setCandidate] = useState(initialCandidate);
  const experiments = useInfiniteQuery({
    queryKey: ["comparison-experiment-options"],
    initialPageParam: 0,
    queryFn: ({ signal, pageParam }) =>
      api!.request<{ items: Experiment[] }>(
        `/v1/experiments?limit=50&offset=${pageParam}`,
        { signal },
      ),
    getNextPageParam: (last, pages) =>
      last.items.length === 50 ? pages.length * 50 : undefined,
  });
  const left = useQuery({
    queryKey: ["experiment", baseline],
    queryFn: ({ signal }) =>
      api!.request<Experiment>(`/v1/experiments/${baseline}`, { signal }),
    enabled: !!baseline,
  });
  const right = useQuery({
    queryKey: ["experiment", candidate],
    queryFn: ({ signal }) =>
      api!.request<Experiment>(`/v1/experiments/${candidate}`, { signal }),
    enabled: !!candidate,
  });
  const options = new Map(
    (experiments.data?.pages.flatMap((p) => p.items) || []).map((e) => [
      e.id,
      e,
    ]),
  );
  if (left.data) options.set(left.data.id, left.data);
  if (right.data) options.set(right.data.id, right.data);
  const [busy, setBusy] = useState(false);
  const error = experiments.error || left.error || right.error;
  return (
    <section className="panel p-5 sm:p-6">
      <div className="flex flex-col gap-6">
        <div>
          <h2>选择实验</h2>
          <p className="muted small-text">
            报告固定生成时的状态。实验仍在运行时可以保存，但门槛可能无法判定。
          </p>
        </div>
        {experiments.isPending ? <Loading label="正在读取实验" /> : null}
        {error && (
          <ErrorNotice
            error={error}
            retry={() => {
              void experiments.refetch();
              if (baseline) void left.refetch();
              if (candidate) void right.refetch();
            }}
          />
        )}
        {!experiments.isPending && !error && !options.size ? (
          <Empty
            title="还没有可比较的实验"
            description="先完成实验，再选择基线与候选结果。"
            action={
              <Link className="text-button" to="/experiments">
                前往实验
              </Link>
            }
          />
        ) : (
          <>
            <FieldGroup className="sm:flex-row">
              {(["baseline", "candidate"] as const).map((side) => (
                <Field key={side} className="field" data-disabled={busy}>
                  <FieldLabel htmlFor={`compare-${side}`}>
                    {side === "baseline" ? "基线实验" : "候选实验"}
                  </FieldLabel>
                  <select
                    id={`compare-${side}`}
                    value={side === "baseline" ? baseline : candidate}
                    disabled={busy}
                    onChange={(event) =>
                      side === "baseline"
                        ? setBaseline(event.target.value)
                        : setCandidate(event.target.value)
                    }
                  >
                    <option value="">选择实验</option>
                    {(side === "baseline" ? baseline : candidate) &&
                      !options.has(
                        side === "baseline" ? baseline : candidate,
                      ) && (
                        <option
                          value={side === "baseline" ? baseline : candidate}
                        >
                          {shortId(side === "baseline" ? baseline : candidate)}{" "}
                          · 正在读取
                        </option>
                      )}
                    {[...options.values()].map((exp) => (
                      <option
                        key={exp.id}
                        value={exp.id}
                        disabled={
                          exp.id ===
                          (side === "baseline" ? candidate : baseline)
                        }
                      >
                        {shortId(exp.id)} · {formatDate(exp.created_at)} ·{" "}
                        {exp.snapshot.target.content.name}
                      </option>
                    ))}
                  </select>
                </Field>
              ))}
            </FieldGroup>
            {experiments.hasNextPage && (
              <Button
                variant="outline"
                disabled={busy || experiments.isFetchingNextPage}
                onClick={() => void experiments.fetchNextPage()}
              >
                {experiments.isFetchingNextPage
                  ? "正在读取…"
                  : "加载更早的实验"}
              </Button>
            )}
            {baseline && candidate && baseline === candidate ? (
              <Alert>
                <AlertTitle>请选择两个不同的实验</AlertTitle>
              </Alert>
            ) : baseline && candidate && (left.isPending || right.isPending) ? (
              <Loading label="正在读取评分口径" />
            ) : left.data && right.data && !left.error && !right.error ? (
              <ReportSettings
                key={`${baseline}:${candidate}`}
                baseline={left.data}
                candidate={right.data}
                onCreated={onCreated}
                busy={busy}
                initialRequest={initialRequest}
                setBusy={setBusy}
              />
            ) : null}
          </>
        )}
      </div>
    </section>
  );
}

function ReportSettings({
  baseline,
  candidate,
  onCreated,
  busy,
  initialRequest,
  setBusy,
}: {
  baseline: Experiment;
  candidate: Experiment;
  onCreated: (id: string) => void;
  busy: boolean;
  initialRequest?: ComparisonRequest;
  setBusy: (value: boolean) => void;
}) {
  const { api } = useConnection();
  const client = useQueryClient();
  const [pairs, setPairs] = useState<Record<string, string>>(() => {
    if (
      initialRequest?.baseline_id === baseline.id &&
      initialRequest.candidate_id === candidate.id
    )
      return Object.fromEntries(
        initialRequest.scorer_pairs.map((pair) => [
          pair.baseline_id,
          pair.candidate_id,
        ]),
      );
    const matches: Record<string, string> = {};
    const used = new Set<string>();
    for (const scorer of baseline.snapshot.scorers) {
      const match = candidate.snapshot.scorers.find(
        (s) => s.digest === scorer.digest && !used.has(s.id),
      );
      if (match && used.size < 20) {
        matches[scorer.id] = match.id;
        used.add(match.id);
      }
    }
    return matches;
  });
  const [gate, setGate] = useState(initialRequest?.gate || defaultGate);
  const [error, setError] = useState<unknown>(null);
  const pending = useRef<{ signature: string; key: string } | null>(null);
  const submitting = useRef(false);
  const selectedPairs = Object.entries(pairs)
    .filter(([, id]) => id)
    .map(([id, other]) => ({ baseline_id: id, candidate_id: other }));
  const changed = selectedPairs.some(
    (p) =>
      baseline.snapshot.scorers.find((s) => s.id === p.baseline_id)?.digest !==
      candidate.snapshot.scorers.find((s) => s.id === p.candidate_id)?.digest,
  );
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (
      !api ||
      submitting.current ||
      !selectedPairs.length ||
      selectedPairs.length > 20
    )
      return;
    submitting.current = true;
    setBusy(true);
    setError(null);
    const body: ComparisonRequest = {
      schema_version: "1.0",
      baseline_id: baseline.id,
      candidate_id: candidate.id,
      scorer_pairs: selectedPairs,
      gate,
    };
    const signature = JSON.stringify(body);
    if (pending.current?.signature !== signature)
      pending.current = { signature, key: crypto.randomUUID() };
    try {
      const report = await api.post<ComparisonReport>("/v1/comparisons", body, {
        "Idempotency-Key": pending.current.key,
      });
      client.setQueryData(["comparison-report", report.id], report);
      void client.invalidateQueries({ queryKey: ["comparison-reports"] });
      onCreated(report.id);
    } catch (failure) {
      setError(failure);
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }
  return (
    <form
      onSubmit={(event) => void submit(event)}
      className="flex flex-col gap-6"
    >
      <div>
        <h2>评分口径配对</h2>
        <p className="muted small-text">
          默认配对内容摘要一致的版本。每个评分器只能使用一次，最多比较 20 组。
        </p>
      </div>
      {!baseline.snapshot.scorers.length ||
      !candidate.snapshot.scorers.length ? (
        <Empty
          compact
          title="实验缺少评分口径"
          description="两侧至少需要各一个评分器，才能生成质量回归报告。"
        />
      ) : (
        <FieldGroup>
          {baseline.snapshot.scorers.map((scorer) => (
            <Field key={scorer.id} className="field" data-disabled={busy}>
              <FieldLabel htmlFor={`scorer-${scorer.id}`}>
                {scorer.content.name} · 基线 {shortId(scorer.id)}
              </FieldLabel>
              <select
                id={`scorer-${scorer.id}`}
                value={pairs[scorer.id] || ""}
                disabled={busy}
                onChange={(event) =>
                  setPairs({ ...pairs, [scorer.id]: event.target.value })
                }
              >
                <option value="">不纳入本报告</option>
                {candidate.snapshot.scorers.map((other) => (
                  <option
                    key={other.id}
                    value={other.id}
                    disabled={selectedPairs.some(
                      (pair) =>
                        pair.candidate_id === other.id &&
                        pair.baseline_id !== scorer.id,
                    )}
                  >
                    {other.content.name} · {shortId(other.id)} ·{" "}
                    {other.digest === scorer.digest ? "同一口径" : "口径变化"}
                  </option>
                ))}
              </select>
            </Field>
          ))}
        </FieldGroup>
      )}
      {changed && (
        <Alert>
          <AlertTitle>已选择不同评分口径</AlertTitle>
          <AlertDescription>
            这些配对会在报告中标为不可比，不会作为同口径的改善或退化。
          </AlertDescription>
        </Alert>
      )}
      <details open>
        <summary>质量门槛</summary>
        <FieldGroup className="mt-4 sm:flex-row sm:flex-wrap">
          {gateFields.map(({ key, label, percent, integer }) => (
            <Field
              key={key}
              className="sm:basis-[30%] sm:grow"
              data-disabled={busy}
            >
              <FieldLabel htmlFor={`gate-${key}`}>{label}</FieldLabel>
              <Input
                id={`gate-${key}`}
                type="number"
                required
                min={0}
                max={percent ? 100 : undefined}
                step={integer ? 1 : "any"}
                disabled={busy}
                defaultValue={
                  (initialRequest?.gate || defaultGate)[key] *
                  (percent ? 100 : 1)
                }
                onChange={(event) =>
                  setGate({
                    ...gate,
                    [key]: event.target.valueAsNumber / (percent ? 100 : 1),
                  })
                }
              />
            </Field>
          ))}
        </FieldGroup>
      </details>
      <FieldDescription>
        {initialRequest &&
          "已保留原报告门槛与原实验的评分器配对；本次重新按默认规则读取评分，不沿用显式指定的历史评分。"}
        每个用例的重复执行先求平均，再按用例等权汇总。默认选择首个成功执行及其最早评分；不会自动采用后来重新评分的结果。
      </FieldDescription>
      {error != null && <ErrorNotice error={error} />}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="muted small-text" role="status">
          已选 {selectedPairs.length} 组评分口径
          {selectedPairs.length > 20 ? "，请减少至 20 组以内" : ""}
          。提交失败后，相同参数重试会复用请求键。
        </span>
        <Button
          type="submit"
          disabled={busy || !selectedPairs.length || selectedPairs.length > 20}
        >
          <GitCompareArrows data-icon="inline-start" />
          {busy ? "正在生成报告…" : "生成固定报告"}
        </Button>
      </div>
    </form>
  );
}
