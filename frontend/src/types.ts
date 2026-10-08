export type Json =
  null | boolean | number | string | Json[] | { [key: string]: Json };
export type Payload = { [key: string]: Json };
export interface RecordBase {
  id: string;
  created_at: string;
}
export interface Version extends RecordBase {
  name: string;
  digest: string;
  content: Payload;
}
export type CatalogKind = "targets" | "datasets" | "scorers";
export interface TargetContent {
  name: string;
  external_version: string | null;
  concurrency_limit: number;
  capabilities: {
    adapter: string;
    observation: string[];
    session_isolation: boolean;
    environment_isolation: boolean;
    cancellation: boolean;
    idempotency: boolean;
    reconciliation: boolean;
  };
  config: Payload;
  secret_refs: Record<string, string>;
}
export interface ScorerContent {
  name: string;
  plugin: string;
  implementation_digest: string;
  config: Payload;
  required_evidence: string[];
  numeric: {
    minimum: number;
    maximum: number;
    threshold: number;
    direction: string;
  } | null;
}
export interface ExperimentRequest {
  target_version_id: string;
  dataset_version_id: string;
  scorer_version_ids: string[];
  concurrency: number;
  timeout_seconds: number;
  repetitions: number;
  attempt_selection: "first_success";
  parent_experiment_id?: string | null;
}
export interface Experiment extends RecordBase {
  batch_id?: string | null;
  status: string;
  target_id: string;
  dataset_id: string;
  snapshot: {
    request: ExperimentRequest;
    target: { id: string; digest: string; content: TargetContent };
    dataset_digest: string;
    scorers: { id: string; digest: string; content: ScorerContent }[];
  };
}
export interface Ratio {
  numerator: number;
  denominator: number;
}
export interface Summary {
  status: string;
  planned_runs: number;
  execution_successes: number;
  execution_attempts: number;
  failed_attempts: number;
  unknown_attempts: number;
  cancelled_runs: number;
  execution_success_rate: Ratio;
  scorers: {
    scorer_version_id: string;
    planned_runs: number;
    valid_scores: number;
    passed: number;
    not_applicable: number;
    unresolved: number;
    score_coverage: Ratio;
    valid_score_pass_rate: Ratio;
  }[];
}
export interface Manifest extends RecordBase {
  version: number;
  digest: string;
  content: {
    status: string;
    dropped_events: number | null;
    references: string[];
    event_ids: string[];
    artifact_ids: string[];
    result: Payload | null;
    [key: string]: Json | undefined;
  };
}
export interface ScoreRun extends RecordBase {
  scorer_id: string;
  manifest_id: string;
  status: string;
  result: {
    status: string;
    verdict: string | null;
    value: number | null;
    reason: string;
    evidence_refs: string[];
  } | null;
}
export interface Attempt extends RecordBase {
  status: string;
  trace_id: string;
  root_span_id: string;
  finished_at: string | null;
  cleanup_status: string;
  evidence_status: string;
  result: {
    output?: Payload;
    error?: string;
    dropped_events?: number;
    [key: string]: Json | undefined;
  } | null;
  score_runs?: ScoreRun[];
  manifests?: Manifest[];
  resolutions?: RecordBase[];
}
export interface CaseRun extends RecordBase {
  repetition: number;
  status: string;
  case: RecordBase & {
    case_id: string;
    digest: string;
    content: { input: Payload; expectations: Payload; tags: string[] };
  };
  attempts: Attempt[];
}
export interface Event extends RecordBase {
  producer_id: string;
  content: {
    type: string;
    source: string;
    sequence: number;
    occurred_at: string;
    span_id: string | null;
    parent_span_id: string | null;
    data: Payload;
    [key: string]: Json;
  };
}
export interface Operations {
  observed_at: string;
  work_counts: { kind: string; status: string; count: number }[];
  runners: (RecordBase & {
    name: string;
    last_seen_at: string;
    capabilities: { adapters?: string[]; scorers?: string[] };
  })[];
}
