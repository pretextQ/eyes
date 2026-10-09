import type { RecordBase, Summary } from "../types";

export type Classification =
  "regressed" | "improved" | "unchanged" | "inconclusive";
export interface GatePolicy {
  max_regressions: number;
  min_comparable_coverage: number;
  min_candidate_pass_rate: number;
  min_execution_success_rate: number;
  numeric_tolerance: number;
}
export interface ComparisonRequest {
  schema_version: "1.0";
  baseline_id: string;
  candidate_id: string;
  scorer_pairs: { baseline_id: string; candidate_id: string }[];
  gate: GatePolicy;
  baseline_score_ids?: string[];
  candidate_score_ids?: string[];
}
export interface ComparisonSide {
  case_run_id: string;
  attempt_id: string | null;
  execution_status: string;
  score_run_id: string | null;
  score_status: string | null;
  manifest_id: string | null;
  manifest_digest: string | null;
  evidence_expired: boolean;
  verdict: string | null;
  value: number | null;
  evidence_refs: string[];
}
export interface ComparisonRow {
  case_id: string;
  repetition: number;
  baseline_scorer_id: string;
  candidate_scorer_id: string;
  baseline: ComparisonSide | null;
  candidate: ComparisonSide | null;
  comparable: boolean;
  reasons: string[];
}
export interface CaseComparison {
  case_id: string;
  repetitions: number;
  classification: Classification;
  baseline_pass_rate?: number;
  candidate_pass_rate?: number;
  pass_rate_delta?: number;
  baseline_value?: number;
  candidate_value?: number;
  numeric_delta?: number;
}
export interface ScorerComparison {
  baseline_scorer_id: string;
  candidate_scorer_id: string;
  baseline_scorer_digest: string;
  candidate_scorer_digest: string;
  planned_cases: number;
  comparable_coverage: {
    numerator: number;
    denominator: number;
    value: number | null;
  };
  candidate_pass_rate: number | null;
  improved: number;
  regressed: number;
  unresolved: number;
  cases: CaseComparison[];
}
export interface ComparisonReport extends RecordBase {
  baseline_id: string;
  candidate_id: string;
  digest: string;
  content: {
    request: ComparisonRequest & {
      baseline_score_ids?: string[];
      candidate_score_ids?: string[];
    };
    selection: string;
    aggregation: string;
    baseline_summary: Summary;
    candidate_summary: Summary;
    configuration_differences: string[];
    warnings: string[];
    scorers: ScorerComparison[];
    rows: ComparisonRow[];
    gate: {
      status: "pass" | "fail" | "inconclusive";
      failures: string[];
      gaps: string[];
      policy: GatePolicy;
    };
  };
}
export const classificationLabels: Record<Classification, string> = {
  regressed: "退化",
  improved: "改善",
  unchanged: "无变化",
  inconclusive: "无法判定",
};
export function percentage(value: number | null | undefined) {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}
const reasons: Record<string, string> = {
  missing_case: "一侧缺少用例",
  case_changed: "用例内容发生变化",
  scorer_changed: "评分口径发生变化",
  target_capabilities: "目标能力或采集范围发生变化",
  execution_not_successful: "执行未成功",
  score_not_completed: "评分未完成",
  not_applicable: "没有适用的有效评分",
  evidence_expired: "证据已过期",
  regression_limit: "退化用例数超过上限",
  comparable_coverage: "可比覆盖率不足",
  no_valid_scores: "没有有效的可比评分",
  pass_rate: "通过率低于门槛",
  experiment_not_finished: "实验尚未结束",
  unknown_execution: "存在结果未知的执行",
  no_candidate_runs: "候选实验没有用例",
  execution_success_rate: "执行成功率低于门槛",
  external_version_unknown: "外部 Agent 版本未知",
  external_environment_limitations: "用例存在无法固定的外部环境",
  concurrency: "并发数变化",
  timeout_seconds: "超时配置变化",
  repetitions: "重复次数变化",
  attempt_selection: "执行选择规则变化",
  evidence_wait_seconds: "证据等待期限变化",
};
export function comparisonReason(
  value: string,
  scorerName?: (id: string) => string,
): string {
  if (value.startsWith("target_configuration_changed"))
    return "目标配置发生变化，请确认它属于本次比较变量。";
  if (value.startsWith("dataset_changed"))
    return "测试集发生变化，服务端按各用例内容判断可比性。";
  if (reasons[value]) return reasons[value];
  const separator = value.indexOf(":");
  if (separator < 0) return value;
  const prefix = value.slice(0, separator),
    detail = value.slice(separator + 1);
  if (prefix === "execution_config") return reasons[detail] || value;
  if (prefix === "external_environment_limitations")
    return `${reasons[prefix]}：${detail}`;
  const label =
    prefix === "baseline"
      ? "基线"
      : prefix === "candidate"
        ? "候选"
        : scorerName?.(prefix) || prefix;
  return `${label}：${reasons[detail] || detail}`;
}
export function evidenceLink(
  report: ComparisonReport,
  side: ComparisonSide,
  baseline: boolean,
) {
  const params = new URLSearchParams({
    view: side.score_run_id ? "scores" : "result",
    report: report.id,
  });
  if (side.attempt_id) params.set("attempt", side.attempt_id);
  else params.set("report_unselected", "1");
  if (side.score_run_id) params.set("score", side.score_run_id);
  return `/experiments/${baseline ? report.baseline_id : report.candidate_id}/cases/${side.case_run_id}?${params}`;
}
