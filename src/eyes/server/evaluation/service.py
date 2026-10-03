import secrets
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from eyes.contracts.scorer import ScoreOutput
from eyes.server.domain import DomainError
from eyes.server.evidence.service import ArtifactStore, view
from eyes.server.storage.models import (
    Artifact,
    Attempt,
    CaseRun,
    CaseVersion,
    EvidenceWait,
    Experiment,
    Manifest,
    ScoreRun,
    ScorerVersion,
    WorkItem,
    now,
)


def missing_evidence(attempt, manifest, scorer):
    evidence = manifest.content
    available = {"input"}
    if (evidence.get("result") or {}).get("output") is not None:
        available.add("output")
    if evidence["event_ids"]:
        available.add("events")
    if evidence["artifact_ids"]:
        available.add("artifacts")
    if evidence["status"] == "sealed" and evidence["dropped_events"] == 0:
        available.add("sealed")
    return set(scorer["required_evidence"]) - available


def enqueue(
    session: Session,
    attempt: Attempt,
    manifest: Manifest,
    scorer_ids=None,
    *,
    allow_wait=False,
    skipped=False,
):
    if attempt.evidence_expired_at:
        raise DomainError(410, "evidence_expired", "expired evidence cannot be scored")
    run = session.get(CaseRun, attempt.case_run_id)
    experiment = session.get(Experiment, run.experiment_id)
    created = []
    for snapshot in experiment.snapshot["scorers"]:
        scorer_id = UUID(snapshot["id"])
        if scorer_ids is not None and scorer_id not in scorer_ids:
            continue
        scorer = snapshot["content"]
        missing = missing_evidence(attempt, manifest, scorer)
        wait_seconds = experiment.snapshot["request"].get("evidence_wait_seconds", 0)
        if missing and allow_wait and wait_seconds:
            session.add(
                EvidenceWait(
                    attempt_id=attempt.id,
                    scorer_id=scorer_id,
                    deadline=now() + timedelta(seconds=wait_seconds),
                )
            )
            continue
        score = ScoreRun(
            attempt_id=attempt.id,
            scorer_id=scorer_id,
            manifest_id=manifest.id,
            trace_id=secrets.token_hex(16),
            root_span_id=secrets.token_hex(8),
        )
        if skipped:
            score.status = "skipped"
            score.result = ScoreOutput(
                status="skipped", reason="experiment cancelled while waiting for evidence"
            ).model_dump(mode="json")
        elif missing:
            score.status = "insufficient_evidence"
            score.result = ScoreOutput(
                status="insufficient_evidence",
                reason="missing required evidence: " + ", ".join(sorted(missing)),
            ).model_dump(mode="json")
        session.add(score)
        session.flush()
        if not missing and not skipped:
            session.add(
                WorkItem(
                    project_id=experiment.project_id,
                    experiment_id=experiment.id,
                    target_id=experiment.target_id,
                    target_scope_id=experiment.target_scope_id,
                    case_run_id=run.id,
                    attempt_id=attempt.id,
                    score_run_id=score.id,
                    kind="score",
                    plugin=scorer["plugin"],
                )
            )
        created.append(score)
    session.flush()
    return created


def score_input(session: Session, score: ScoreRun):
    attempt = session.get(Attempt, score.attempt_id)
    run = session.get(CaseRun, attempt.case_run_id)
    manifest = session.get(Manifest, score.manifest_id)
    if attempt.evidence_expired_at:
        raise DomainError(410, "evidence_expired", "evidence payloads have expired")
    return {
        "schema_version": "1.0",
        "score_run_id": score.id,
        "attempt_id": attempt.id,
        "case": session.get(CaseVersion, run.case_version_id).content,
        "result": manifest.content["result"],
        "evidence": view(session, manifest),
        "scorer": session.get(ScorerVersion, score.scorer_id).content,
        "traceparent": f"00-{score.trace_id}-{score.root_span_id}-01",
        "execution_trace_id": attempt.trace_id,
        "execution_root_span_id": attempt.root_span_id,
        "deadline": score.deadline,
    }


def complete(session: Session, score: ScoreRun, output: ScoreOutput, store: ArtifactStore):
    manifest = session.get(Manifest, score.manifest_id)
    if set(output.evidence_refs) - set(manifest.content["references"]):
        raise DomainError(
            422, "invalid_evidence_reference", "score cites evidence outside its manifest"
        )
    for reference in output.evidence_refs:
        if reference.startswith("artifact:"):
            artifact = session.get(Artifact, UUID(reference.removeprefix("artifact:")))
            if (
                artifact is None
                or artifact.attempt_id != score.attempt_id
                or (artifact.status != "ready" or not store.path(artifact.storage_key).is_file())
            ):
                raise DomainError(422, "evidence_unavailable", "cited artifact is not readable")
    scorer = session.get(ScorerVersion, score.scorer_id).content
    semantics = scorer["numeric"]
    if output.value is not None:
        if semantics is None:
            raise DomainError(422, "undeclared_score", "scorer has not declared numeric semantics")
        if not semantics["minimum"] <= output.value <= semantics["maximum"]:
            raise DomainError(422, "score_range", "numeric score is outside declared range")
        if output.verdict not in {"pass", "fail"}:
            raise DomainError(422, "score_verdict", "numeric score requires pass/fail")
        passes = (
            output.value >= semantics["threshold"]
            if semantics["direction"] == "higher"
            else output.value <= semantics["threshold"]
        )
        if (output.verdict == "pass") != passes:
            raise DomainError(422, "score_threshold", "verdict contradicts numeric threshold")
    elif semantics is not None and output.verdict in {"pass", "fail"}:
        raise DomainError(422, "missing_score", "numeric scorer requires a value")
    score.status = output.status
    score.result = output.model_dump(mode="json")
    session.flush()


def rescore(session: Session, attempt: Attempt):
    if session.scalar(
        select(EvidenceWait.id).where(
            EvidenceWait.attempt_id == attempt.id, EvidenceWait.status == "waiting"
        )
    ):
        raise DomainError(409, "evidence_waiting", "initial scoring is still waiting for evidence")
    if attempt.status != "succeeded":
        raise DomainError(409, "execution_not_successful", "ordinary re-scoring requires success")
    manifest = session.scalar(
        select(Manifest)
        .where(Manifest.attempt_id == attempt.id)
        .order_by(Manifest.version.desc())
        .limit(1)
    )
    if manifest is None:
        raise DomainError(409, "missing_manifest", "evidence manifest is not available")
    return enqueue(session, attempt, manifest)


def advance_waits(session, *, experiment_id=None, cancel=False):
    query = select(EvidenceWait).join(Attempt).join(CaseRun).where(EvidenceWait.status == "waiting")
    if experiment_id is not None:
        query = query.where(CaseRun.experiment_id == experiment_id)
    changed = set()
    for wait in session.scalars(
        query.order_by(EvidenceWait.deadline, EvidenceWait.id).with_for_update(of=EvidenceWait)
    ):
        attempt = session.scalar(
            select(Attempt).where(Attempt.id == wait.attempt_id).with_for_update()
        )
        manifest = session.scalar(
            select(Manifest)
            .where(
                Manifest.attempt_id == attempt.id,
                Manifest.created_at <= (now() if cancel else min(now(), wait.deadline)),
            )
            .order_by(Manifest.version.desc())
            .limit(1)
        )
        scorer = session.get(ScorerVersion, wait.scorer_id)
        if (
            cancel
            or wait.deadline <= now()
            or not missing_evidence(attempt, manifest, scorer.content)
        ):
            enqueue(session, attempt, manifest, [wait.scorer_id], skipped=cancel)
            wait.status = "cancelled" if cancel else "completed"
            changed.add(session.get(CaseRun, attempt.case_run_id).experiment_id)
    session.flush()
    return changed


def retry(session, project_id, score_id):
    original = session.scalar(
        select(ScoreRun)
        .join(Attempt)
        .where(ScoreRun.id == score_id, Attempt.project_id == project_id)
    )
    if original is None:
        raise DomainError(404, "not_found", "score not found in this project")
    if original.status != "error":
        raise DomainError(409, "score_not_failed", "only scorer errors can be retried")
    attempt = session.get(Attempt, original.attempt_id)
    manifest = session.get(Manifest, original.manifest_id)
    # A retry keeps precisely the same evidence; explicit rescore selects newer evidence.
    scores = enqueue(session, attempt, manifest, [original.scorer_id])
    return scores[0]
