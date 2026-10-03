"""Persist reproducible comparisons; never replace published reports or scores."""

from collections import defaultdict
from statistics import mean
from uuid import UUID

from sqlalchemy import select

from eyes.contracts.comparison import ComparisonCreate
from eyes.server.domain import DomainError, digest, scoped
from eyes.server.experiments.service import summary
from eyes.server.storage.database import scheduling_lock
from eyes.server.storage.models import (
    Attempt,
    CaseRun,
    CaseVersion,
    ComparisonReport,
    Experiment,
    Manifest,
    ScoreRun,
)


def capture(session, experiment, overrides, scorer_ids):
    runs = session.scalars(select(CaseRun).where(CaseRun.experiment_id == experiment.id)).all()
    cases = {
        c.id: c
        for c in session.scalars(
            select(CaseVersion).where(CaseVersion.dataset_id == experiment.dataset_id)
        )
    }
    attempts = session.scalars(
        select(Attempt)
        .join(CaseRun)
        .where(CaseRun.experiment_id == experiment.id)
        .order_by(Attempt.created_at, Attempt.id)
    ).all()
    selected = {}
    for attempt in attempts:
        if attempt.status == "succeeded":
            selected.setdefault(attempt.case_run_id, attempt)
    selected_ids = {attempt.id for attempt in selected.values()}
    scores = session.scalars(
        select(ScoreRun)
        .join(Attempt)
        .join(CaseRun)
        .where(CaseRun.experiment_id == experiment.id)
        .order_by(ScoreRun.created_at, ScoreRun.id)
    ).all()
    eligible = {
        s.id: s for s in scores if s.attempt_id in selected_ids and s.scorer_id in scorer_ids
    }
    chosen = {}
    for score in eligible.values():
        chosen.setdefault((score.attempt_id, score.scorer_id), score)
    overridden = set()
    for sid in overrides:
        score = eligible.get(sid)
        if score is None:
            raise DomainError(
                422, "score_selection", "score override is outside selected attempts/scorers"
            )
        key = (score.attempt_id, score.scorer_id)
        if key in overridden:
            raise DomainError(
                422, "score_selection", "only one score per attempt/scorer is allowed"
            )
        overridden.add(key)
        chosen[key] = score
    result = {}
    for run in runs:
        case = cases[run.case_version_id]
        attempt = selected.get(run.id)
        for scorer_id in scorer_ids:
            score = chosen.get((attempt.id, scorer_id)) if attempt else None
            manifest = session.get(Manifest, score.manifest_id) if score else None
            result[(case.case_id, run.repetition, scorer_id)] = {
                "case_digest": case.digest,
                "case_run_id": str(run.id),
                "case_environment_limitations": case.content.get("environment_limitations", []),
                "attempt_id": str(attempt.id) if attempt else None,
                "execution_status": attempt.status if attempt else run.status,
                "score_run_id": str(score.id) if score else None,
                "score_status": score.status if score else None,
                "manifest_id": str(manifest.id) if manifest else None,
                "manifest_digest": manifest.digest if manifest else None,
                "evidence_expired": bool(attempt and attempt.evidence_expired_at),
                "verdict": (score.result or {}).get("verdict") if score else None,
                "value": (score.result or {}).get("value") if score else None,
                "evidence_refs": (score.result or {}).get("evidence_refs", []) if score else [],
            }
    return result, summary(session, experiment)


def rate(numerator, denominator):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def create(session, project_id, key, request: ComparisonCreate):
    # Completion, rescore, cancellation, expiration and report capture share this
    # lock, so one report observes one stable selection of published scores.
    scheduling_lock(session)
    request_content = request.model_dump(mode="json")
    request_digest = digest(request_content)
    previous = session.scalar(
        select(ComparisonReport).where(
            ComparisonReport.project_id == project_id, ComparisonReport.request_key == key
        )
    )
    if previous:
        if previous.request_digest != request_digest:
            raise DomainError(
                409, "idempotency_conflict", "same key has different comparison parameters"
            )
        return previous
    baseline = scoped(session, Experiment, request.baseline_id, project_id)
    candidate = scoped(session, Experiment, request.candidate_id, project_id)
    versions = [{UUID(s["id"]): s for s in e.snapshot["scorers"]} for e in (baseline, candidate)]
    for pair in request.scorer_pairs:
        if pair.baseline_id not in versions[0] or pair.candidate_id not in versions[1]:
            raise DomainError(422, "scorer_pair", "scorer must belong to its experiment snapshot")
    left, left_summary = capture(
        session, baseline, request.baseline_score_ids, {p.baseline_id for p in request.scorer_pairs}
    )
    right, right_summary = capture(
        session,
        candidate,
        request.candidate_score_ids,
        {p.candidate_id for p in request.scorer_pairs},
    )
    a, b = baseline.snapshot, candidate.snapshot
    differences = []
    for field in (
        "concurrency",
        "timeout_seconds",
        "repetitions",
        "attempt_selection",
        "evidence_wait_seconds",
    ):
        default = 0 if field == "evidence_wait_seconds" else None
        if a["request"].get(field, default) != b["request"].get(field, default):
            differences.append(f"execution_config:{field}")
    if a["target"]["content"]["capabilities"] != b["target"]["content"]["capabilities"]:
        differences.append("target_capabilities")
    warnings = []
    if a["target"]["content"]["config"] != b["target"]["content"]["config"]:
        warnings.append("target_configuration_changed; review the intended comparison variable")
    if a["dataset_digest"] != b["dataset_digest"]:
        warnings.append("dataset_changed; individual case digests determine comparability")
    if any(
        not e.snapshot["target"]["content"].get("external_version") for e in (baseline, candidate)
    ):
        warnings.append("external_version_unknown")
    rows, aggregates = [], []
    for pair in request.scorer_pairs:
        av, bv = versions[0][pair.baseline_id], versions[1][pair.candidate_id]
        pair_differences = differences + (
            [] if av["digest"] == bv["digest"] else ["scorer_changed"]
        )
        keys = sorted(
            {(c, r) for c, r, s in left if s == pair.baseline_id}
            | {(c, r) for c, r, s in right if s == pair.candidate_id}
        )
        groups = defaultdict(list)
        for case_id, repetition in keys:
            x, y = (
                left.get((case_id, repetition, pair.baseline_id)),
                right.get((case_id, repetition, pair.candidate_id)),
            )
            reasons = list(pair_differences)
            if x is None or y is None:
                reasons.append("missing_case")
            else:
                if x["case_digest"] != y["case_digest"]:
                    reasons.append("case_changed")
                if x["case_environment_limitations"] or y["case_environment_limitations"]:
                    warnings.append(f"external_environment_limitations:{case_id}")
                for label, side in (("baseline", x), ("candidate", y)):
                    if side["execution_status"] != "succeeded":
                        reasons.append(f"{label}:execution_not_successful")
                    elif side["score_status"] != "completed":
                        reasons.append(f"{label}:score_not_completed")
                    elif side["verdict"] not in {"pass", "fail"}:
                        reasons.append(f"{label}:not_applicable")
                    if side["evidence_expired"]:
                        reasons.append(f"{label}:evidence_expired")
            row = {
                "case_id": case_id,
                "repetition": repetition,
                "baseline_scorer_id": str(pair.baseline_id),
                "candidate_scorer_id": str(pair.candidate_id),
                "baseline": x,
                "candidate": y,
                "reasons": reasons,
                "comparable": not reasons,
            }
            rows.append(row)
            groups[case_id].append(row)
        cases = []
        for case_id, repetitions in groups.items():
            item = {
                "case_id": case_id,
                "repetitions": len(repetitions),
                "classification": "inconclusive",
            }
            if all(r["comparable"] for r in repetitions):
                ap = mean(r["baseline"]["verdict"] == "pass" for r in repetitions)
                bp = mean(r["candidate"]["verdict"] == "pass" for r in repetitions)
                delta = bp - ap
                item.update(baseline_pass_rate=ap, candidate_pass_rate=bp, pass_rate_delta=delta)
                numeric = av["content"].get("numeric")
                numeric_delta = 0
                if numeric:
                    ax = mean(r["baseline"]["value"] for r in repetitions)
                    bx = mean(r["candidate"]["value"] for r in repetitions)
                    numeric_delta = (bx - ax) * (1 if numeric["direction"] == "higher" else -1)
                    item.update(baseline_value=ax, candidate_value=bx, numeric_delta=bx - ax)
                item["classification"] = (
                    "regressed"
                    if delta < 0 or numeric_delta < -request.gate.numeric_tolerance
                    else "improved"
                    if delta > 0 or numeric_delta > request.gate.numeric_tolerance
                    else "unchanged"
                )
            cases.append(item)
        comparable = [c for c in cases if c["classification"] != "inconclusive"]
        aggregates.append(
            {
                "baseline_scorer_id": str(pair.baseline_id),
                "candidate_scorer_id": str(pair.candidate_id),
                "baseline_scorer_digest": av["digest"],
                "candidate_scorer_digest": bv["digest"],
                "cases": cases,
                "planned_cases": len(cases),
                "comparable_coverage": rate(len(comparable), len(cases)),
                "improved": sum(c["classification"] == "improved" for c in cases),
                "regressed": sum(c["classification"] == "regressed" for c in cases),
                "unresolved": len(cases) - len(comparable),
                "candidate_pass_rate": mean(c["candidate_pass_rate"] for c in comparable)
                if comparable
                else None,
            }
        )
    failures, gaps = [], []
    for aggregate in aggregates:
        label = aggregate["candidate_scorer_id"]
        if aggregate["regressed"] > request.gate.max_regressions:
            failures.append(f"{label}:regression_limit")
        coverage = aggregate["comparable_coverage"]["value"]
        if coverage is None or coverage < request.gate.min_comparable_coverage:
            gaps.append(f"{label}:comparable_coverage")
        passing = aggregate["candidate_pass_rate"]
        if passing is None:
            gaps.append(f"{label}:no_valid_scores")
        elif passing < request.gate.min_candidate_pass_rate:
            failures.append(f"{label}:pass_rate")
    terminal = {"completed", "completed_with_unresolved"}
    if baseline.status not in terminal or candidate.status not in terminal:
        gaps.append("experiment_not_finished")
    if left_summary["unknown_attempts"] or right_summary["unknown_attempts"]:
        gaps.append("unknown_execution")
    execution = rate(right_summary["execution_successes"], right_summary["planned_runs"])
    if execution["value"] is None:
        gaps.append("no_candidate_runs")
    elif (
        candidate.status in terminal
        and execution["value"] < request.gate.min_execution_success_rate
    ):
        failures.append("execution_success_rate")
    content = {
        "schema_version": "1.0",
        "request": request_content,
        "selection": "first_success; earliest score unless explicitly overridden",
        "aggregation": "mean within each case, equal case weight; no significance claim",
        "baseline_summary": left_summary,
        "candidate_summary": right_summary,
        "configuration_differences": differences,
        "warnings": sorted(set(warnings)),
        "scorers": aggregates,
        "rows": rows,
        "gate": {
            "status": "fail" if failures else "inconclusive" if gaps else "pass",
            "failures": failures,
            "gaps": gaps,
            "policy": request.gate.model_dump(mode="json"),
        },
    }
    report = ComparisonReport(
        project_id=project_id,
        baseline_id=baseline.id,
        candidate_id=candidate.id,
        request_key=key,
        request_digest=request_digest,
        content=content,
        digest=digest(content),
    )
    session.add(report)
    session.flush()
    return report
