import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowUpRight, Download } from "lucide-react";
import { useConnection } from "../connection";
import { formatDate, formatRatio, shortId } from "../format";
import type { Experiment } from "../types";
import {
  Badge as StatusBadge,
  Empty,
  ErrorNotice,
  JsonBlock,
  Metrics,
  Pagination,
} from "./ui";
import { Badge } from "./ui/badge";
import { Button, buttonVariants } from "./ui/button";
import { Alert, AlertTitle, AlertDescription } from "./ui/alert";
import { Field, FieldGroup, FieldLabel } from "./ui/field";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "./ui/table";
import {
  classificationLabels,
  comparisonReason,
  evidenceLink,
  percentage,
  type Classification,
  type ComparisonReport,
  type ComparisonSide,
  type ScorerComparison,
} from "@/lib/comparison";

export function GateBadge({
  status,
}: {
  status: ComparisonReport["content"]["gate"]["status"];
}) {
  return (
    <Badge
      variant={
        status === "pass"
          ? "success"
          : status === "fail"
            ? "destructive"
            : "warning"
      }
    >
      {status === "pass"
        ? "门槛通过"
        : status === "fail"
          ? "门槛未通过"
          : "无法判定"}
    </Badge>
  );
}
function ChangeBadge({ value }: { value: Classification }) {
  return (
    <Badge
      variant={
        value === "regressed"
          ? "destructive"
          : value === "improved"
            ? "success"
            : value === "inconclusive"
              ? "warning"
              : "secondary"
      }
    >
      {classificationLabels[value]}
    </Badge>
  );
}

export function ComparisonReportView({ report }: { report: ComparisonReport }) {
  const titleRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    titleRef.current?.focus();
  }, [report.id]);
  const { api } = useConnection();
  const left = useQuery({
    queryKey: ["experiment", report.baseline_id],
    queryFn: ({ signal }) =>
      api!.request<Experiment>(`/v1/experiments/${report.baseline_id}`, {
        signal,
      }),
  });
  const right = useQuery({
    queryKey: ["experiment", report.candidate_id],
    queryFn: ({ signal }) =>
      api!.request<Experiment>(`/v1/experiments/${report.candidate_id}`, {
        signal,
      }),
  });
  const {
    gate,
    scorers,
    warnings,
    configuration_differences: differences,
  } = report.content;
  const scorerName = (id: string) =>
    [
      ...(left.data?.snapshot.scorers || []),
      ...(right.data?.snapshot.scorers || []),
    ].find((s) => s.id === id)?.content.name || shortId(id);
  function download() {
    const blob = new Blob([JSON.stringify(report, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `eyes-comparison-${report.id}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <div className="flex min-w-0 flex-col gap-6">
      <section className="panel p-5 sm:p-6" aria-label="报告结论">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 flex-col gap-2">
            <GateBadge status={gate.status} />
            <h2 ref={titleRef} tabIndex={-1}>
              回归报告 · {shortId(report.id)}
            </h2>
            <p className="muted small-text">
              {formatDate(report.created_at)} ·
              已固定，后续执行与重评分不会改变本报告
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={download}>
              <Download data-icon="inline-start" />
              导出 JSON
            </Button>
            <Link
              className={buttonVariants({ variant: "outline" })}
              to={`/comparison?new=1&source=${report.id}`}
            >
              重新比较当前结果
            </Link>
          </div>
        </div>
        <div className="mt-5 flex flex-col gap-4 sm:flex-row">
          {([true, false] as const).map((baseline) => {
            const exp = baseline ? left.data : right.data;
            const id = baseline ? report.baseline_id : report.candidate_id;
            const summary = baseline
              ? report.content.baseline_summary
              : report.content.candidate_summary;
            return (
              <div className="min-w-0 flex-1" key={id}>
                <p className="section-label">
                  {baseline ? "基线实验" : "候选实验"}
                </p>
                <Link className="text-button" to={`/experiments/${id}`}>
                  {exp?.snapshot.target.content.name || shortId(id)} ·{" "}
                  {shortId(id)}
                  <ArrowUpRight size={14} />
                </Link>
                <p className="muted small-text">
                  {exp?.snapshot.target.content.external_version ||
                    "外部版本未知"}{" "}
                  · 报告时执行成功 {summary.execution_successes}/
                  {summary.planned_runs}
                </p>
                <StatusBadge status={summary.status} />
              </div>
            );
          })}
        </div>
        {(left.error || right.error) && (
          <ErrorNotice
            error={left.error || right.error}
            retry={() => {
              void left.refetch();
              void right.refetch();
            }}
          />
        )}
        <div className="mt-5">
          <Alert variant={gate.status === "fail" ? "destructive" : "default"}>
            <AlertTitle>
              {gate.status === "pass"
                ? "已满足本报告的全部质量门槛"
                : gate.status === "fail"
                  ? "存在明确未达标项"
                  : "当前证据不足以给出通过结论"}
            </AlertTitle>
            <AlertDescription>
              {gate.failures.length > 0 && (
                <div>
                  <strong>未达标项</strong>
                  <ul className="list-disc pl-5">
                    {gate.failures.map((reason) => (
                      <li key={reason}>
                        {comparisonReason(reason, scorerName)}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {gate.gaps.length > 0 && (
                <div>
                  <strong>未解决项</strong>
                  <ul className="list-disc pl-5">
                    {gate.gaps.map((reason) => (
                      <li key={reason}>
                        {comparisonReason(reason, scorerName)}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {gate.status === "pass" && (
                <p>
                  结论按下方固定门槛计算。允许的退化数量和覆盖率取决于本报告配置。
                </p>
              )}
            </AlertDescription>
          </Alert>
        </div>
        <details className="mt-4">
          <summary>查看固定门槛与评分选择</summary>
          <div className="mt-3 flex flex-col gap-2 small-text">
            <p>
              每组允许退化 ≤ {gate.policy.max_regressions}；可比覆盖率 ≥{" "}
              {percentage(gate.policy.min_comparable_coverage)}；候选通过率 ≥{" "}
              {percentage(gate.policy.min_candidate_pass_rate)}；候选执行成功率
              ≥ {percentage(gate.policy.min_execution_success_rate)}；数值容差{" "}
              {gate.policy.numeric_tolerance}。
            </p>
            <p>
              执行取首个成功尝试；评分默认取最早记录。显式指定评分：基线{" "}
              {report.content.request.baseline_score_ids?.length || 0} 条，候选{" "}
              {report.content.request.candidate_score_ids?.length || 0}{" "}
              条。每个用例内的重复先平均，用例之间等权，不代表统计显著性。
            </p>
            <p className="break-all muted">报告摘要：{report.digest}</p>
            <JsonBlock
              title="报告请求与选择规则"
              value={{
                request: report.content.request,
                selection: report.content.selection,
                aggregation: report.content.aggregation,
              }}
            />
          </div>
        </details>
      </section>
      {(warnings.length > 0 || differences.length > 0) && (
        <Alert>
          <AlertTitle>比较条件与可比性提示</AlertTitle>
          <AlertDescription>
            <ul className="list-disc pl-5">
              {[...differences, ...warnings].map((reason) => (
                <li key={reason}>{comparisonReason(reason, scorerName)}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}
      {!scorers.length ? (
        <Empty
          title="报告没有评分口径"
          description="请核对报告内容与创建参数。"
        />
      ) : (
        scorers.map((scorer) => (
          <ScorerResults
            key={scorer.baseline_scorer_id}
            report={report}
            scorer={scorer}
            name={`${scorerName(scorer.baseline_scorer_id)} → ${scorerName(scorer.candidate_scorer_id)}`}
          />
        ))
      )}
      <details>
        <summary>完整固定报告</summary>
        <JsonBlock value={report} title="回归报告 JSON" />
      </details>
    </div>
  );
}

function ScorerResults({
  report,
  scorer,
  name,
}: {
  report: ComparisonReport;
  scorer: ScorerComparison;
  name: string;
}) {
  const [filter, setFilter] = useState("all");
  const [page, setPage] = useState(0);
  const cases = scorer.cases.filter(
    (item) => filter === "all" || item.classification === filter,
  );
  const rowsByCase = new Map<string, typeof report.content.rows>();
  for (const row of report.content.rows) {
    if (
      row.baseline_scorer_id === scorer.baseline_scorer_id &&
      row.candidate_scorer_id === scorer.candidate_scorer_id
    ) {
      const rows = rowsByCase.get(row.case_id) || [];
      rows.push(row);
      rowsByCase.set(row.case_id, rows);
    }
  }
  return (
    <section className="panel">
      <div className="panel-toolbar">
        <div>
          <h2 className="toolbar-title">{name}</h2>
          <p className="muted small-text">
            {shortId(scorer.baseline_scorer_id)} →{" "}
            {shortId(scorer.candidate_scorer_id)}
          </p>
        </div>
        <span className="count">{scorer.planned_cases} 个用例</span>
      </div>
      <Metrics
        items={[
          {
            label: "退化 / 改善",
            value: `${scorer.regressed} / ${scorer.improved}`,
            note: "按用例汇总，重复执行不重复计数",
          },
          {
            label: "可比覆盖率",
            value: percentage(scorer.comparable_coverage.value),
            note: `${scorer.comparable_coverage.numerator} / ${scorer.comparable_coverage.denominator} 个用例`,
          },
          {
            label: "候选通过率",
            value: percentage(scorer.candidate_pass_rate),
            note: "仅对可比用例等权平均",
          },
          {
            label: "无法判定",
            value: scorer.unresolved,
            note: "缺失、口径变化或无有效评分",
          },
        ]}
      />
      <div className="p-4">
        <FieldGroup>
          <Field className="field sm:max-w-xs">
            <FieldLabel htmlFor={`filter-${scorer.baseline_scorer_id}`}>
              筛选变化
            </FieldLabel>
            <select
              id={`filter-${scorer.baseline_scorer_id}`}
              value={filter}
              onChange={(event) => {
                setFilter(event.target.value);
                setPage(0);
              }}
            >
              <option value="all">全部用例</option>
              {Object.entries(classificationLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
        </FieldGroup>
      </div>
      {!cases.length ? (
        <Empty
          compact
          title="没有匹配的用例"
          description="切换筛选条件查看其他结果。"
        />
      ) : (
        <Table
          containerProps={{
            tabIndex: 0,
            role: "region",
            "aria-label": `${name} 用例变化，可横向滚动`,
          }}
        >
          <TableHeader>
            <TableRow>
              <TableHead>用例</TableHead>
              <TableHead>结论</TableHead>
              <TableHead>基线 → 候选通过率</TableHead>
              <TableHead>数值变化</TableHead>
              <TableHead>执行证据 / 不可比原因</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {cases.slice(page * 50, (page + 1) * 50).map((item) => (
              <TableRow key={item.case_id}>
                <TableCell>
                  <strong>{item.case_id}</strong>
                  <div className="muted small-text">
                    {item.repetitions} 次重复
                  </div>
                </TableCell>
                <TableCell>
                  <ChangeBadge value={item.classification} />
                </TableCell>
                <TableCell>
                  {percentage(item.baseline_pass_rate)} →{" "}
                  {percentage(item.candidate_pass_rate)}
                </TableCell>
                <TableCell>
                  {item.numeric_delta == null
                    ? "—"
                    : `${item.numeric_delta > 0 ? "+" : ""}${Number(item.numeric_delta.toPrecision(6))}`}
                  {item.numeric_delta != null && (
                    <div className="muted small-text">
                      {item.baseline_value} → {item.candidate_value}
                    </div>
                  )}
                </TableCell>
                <TableCell>
                  <details>
                    <summary>
                      查看 {item.repetitions} 次执行
                      {item.classification === "inconclusive"
                        ? "与原因"
                        : "与评分"}
                    </summary>
                    <div className="mt-3 flex flex-col gap-4">
                      {(rowsByCase.get(item.case_id) || []).map((row) => (
                        <div
                          key={row.repetition}
                          className="flex flex-col gap-2"
                        >
                          <strong>重复 {row.repetition + 1}</strong>
                          {row.reasons.length > 0 && (
                            <ul className="list-disc pl-4">
                              {row.reasons.map((reason) => (
                                <li key={reason}>{comparisonReason(reason)}</li>
                              ))}
                            </ul>
                          )}
                          <EvidenceSide
                            report={report}
                            side={row.baseline}
                            baseline
                          />
                          <EvidenceSide
                            report={report}
                            side={row.candidate}
                            baseline={false}
                          />
                        </div>
                      ))}
                    </div>
                  </details>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <Pagination
        page={page}
        next={cases.length > (page + 1) * 50}
        onPage={setPage}
      />
      <p className="muted small-text px-4 pb-4">
        候选实验整体执行成功率：
        {formatRatio(report.content.candidate_summary.execution_success_rate)}
        。数值变化为候选减基线，好坏方向由评分口径决定。
      </p>
    </section>
  );
}

function EvidenceSide({
  report,
  side,
  baseline,
}: {
  report: ComparisonReport;
  side: ComparisonSide | null;
  baseline: boolean;
}) {
  const label = baseline ? "基线" : "候选";
  if (!side) return <span className="muted">{label}：缺少用例</span>;
  return (
    <div className="flex flex-col gap-1">
      <div className="flex flex-wrap items-center gap-2">
        <Link className="text-button" to={evidenceLink(report, side, baseline)}>
          {side.attempt_id ? `${label}执行与评分` : `${label}用例历史`}
          <ArrowUpRight size={14} />
        </Link>
        <StatusBadge
          status={side.verdict || side.score_status || side.execution_status}
        />
      </div>
      <span className="muted small-text">
        {side.attempt_id
          ? `Attempt ${shortId(side.attempt_id)}`
          : "报告未选出成功执行"}{" "}
        ·{" "}
        {side.score_run_id
          ? `Score ${shortId(side.score_run_id)}`
          : "报告未选出评分"}
      </span>
      {side.evidence_expired && <span>生成报告时证据已过期</span>}
      {side.manifest_id && (
        <span className="muted small-text">
          固定清单 {shortId(side.manifest_id)} · {side.evidence_refs.length}{" "}
          条评分引用
        </span>
      )}
    </div>
  );
}
