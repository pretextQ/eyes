from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from eyes.contracts.work import ExperimentCreate
from eyes.server.config import Settings
from eyes.server.domain import DomainError, digest, public_record, scoped
from eyes.server.storage.models import (
    Attempt,
    CaseRun,
    CaseVersion,
    DatasetVersion,
    Experiment,
    Manifest,
    Project,
    ScoreRun,
    ScorerVersion,
    TargetVersion,
    WorkItem,
)


def create(
    session: Session, project_id: UUID, key: str, request: ExperimentCreate, settings: Settings
):
    # Serializes duplicate keys including concurrent initial requests. This lock is
    # only used for creation; execution reservations use scheduling advisory locks.
    session.scalar(select(Project).where(Project.id == project_id).with_for_update())
    content = request.model_dump(mode="json")
    request_digest = digest(content)
    previous = session.scalar(
        select(Experiment).where(Experiment.project_id == project_id, Experiment.request_key == key)
    )
    if previous:
        retry_digest = request_digest
        if (
            "evidence_wait_seconds" not in previous.snapshot["request"]
            and "evidence_wait_seconds" not in request.model_fields_set
        ):
            retry_digest = digest(
                {k: v for k, v in content.items() if k != "evidence_wait_seconds"}
            )
        if previous.request_digest != retry_digest:
            raise DomainError(409, "idempotency_conflict", "same key has different parameters")
        return previous
    if len(set(request.scorer_version_ids)) != len(request.scorer_version_ids):
        raise DomainError(422, "duplicate_scorer", "scorer versions must be unique")
    target = scoped(session, TargetVersion, request.target_version_id, project_id)
    dataset = scoped(session, DatasetVersion, request.dataset_version_id, project_id)
    scorers = [
        scoped(session, ScorerVersion, sid, project_id) for sid in request.scorer_version_ids
    ]
    if request.parent_experiment_id:
        scoped(session, Experiment, request.parent_experiment_id, project_id)
    if request.concurrency > target.content["concurrency_limit"]:
        raise DomainError(422, "target_concurrency", "experiment exceeds target concurrency")
    cases = session.scalars(
        select(CaseVersion)
        .where(CaseVersion.dataset_id == dataset.id)
        .order_by(CaseVersion.case_id)
    ).all()
    if len(cases) * request.repetitions > settings.max_experiment_runs:
        raise DomainError(413, "too_many_runs", "experiment exceeds configured run limit")
    experiment = Experiment(
        project_id=project_id,
        target_id=target.id,
        target_scope_id=target.target_id,
        dataset_id=dataset.id,
        request_key=key,
        request_digest=request_digest,
        snapshot={
            "schema_version": "1.0",
            "request": content,
            "target": {"id": str(target.id), "digest": target.digest, "content": target.content},
            "dataset_digest": dataset.digest,
            "scorers": [
                {"id": str(s.id), "digest": s.digest, "content": s.content} for s in scorers
            ],
        },
    )
    session.add(experiment)
    session.flush()
    runs = []
    for case in cases:
        for repetition in range(request.repetitions):
            run = CaseRun(
                experiment_id=experiment.id, case_version_id=case.id, repetition=repetition
            )
            runs.append(run)
    session.add_all(runs)
    session.flush()
    session.add_all(
        [
            WorkItem(
                project_id=project_id,
                experiment_id=experiment.id,
                target_id=target.id,
                target_scope_id=target.target_id,
                case_run_id=run.id,
                kind="execute",
                plugin=target.content["capabilities"]["adapter"],
            )
            for run in runs
        ]
    )
    session.flush()
    return experiment


def summary(session: Session, experiment: Experiment):
    runs = session.scalars(select(CaseRun).where(CaseRun.experiment_id == experiment.id)).all()
    attempts = session.scalars(
        select(Attempt)
        .join(CaseRun)
        .where(CaseRun.experiment_id == experiment.id)
        .order_by(Attempt.created_at, Attempt.id)
    ).all()
    scores = session.scalars(
        select(ScoreRun)
        .join(Attempt)
        .join(CaseRun)
        .where(CaseRun.experiment_id == experiment.id)
        .order_by(ScoreRun.created_at, ScoreRun.id)
    ).all()
    selected = {}
    for attempt in attempts:
        if attempt.status == "succeeded":
            selected.setdefault(attempt.case_run_id, attempt.id)
    planned = len(runs)
    succeeded = len(selected)
    selected_ids = set(selected.values())
    scorer_summaries = []
    for scorer in experiment.snapshot["scorers"]:
        # Stable first published score per selected attempt. Re-scoring history is
        # exposed separately; it cannot silently replace the original aggregate.
        chosen = {}
        for score in scores:
            if str(score.scorer_id) == scorer["id"] and score.attempt_id in selected_ids:
                chosen.setdefault(score.attempt_id, score)
        valid = [
            s
            for s in chosen.values()
            if s.result and s.result.get("verdict") in {"pass", "fail"} and s.status == "completed"
        ]
        passed = sum(s.result["verdict"] == "pass" for s in valid)
        na = sum(
            bool(s.result and s.result.get("verdict") == "not_applicable") for s in chosen.values()
        )
        scorer_summaries.append(
            {
                "scorer_version_id": scorer["id"],
                "planned_runs": planned,
                "valid_scores": len(valid),
                "passed": passed,
                "not_applicable": na,
                "unresolved": max(0, planned - len(valid) - na),
                "score_coverage": {"numerator": len(valid), "denominator": planned},
                "valid_score_pass_rate": {"numerator": passed, "denominator": len(valid)},
            }
        )
    return {
        "schema_version": "1.0",
        "experiment_id": str(experiment.id),
        "status": experiment.status,
        "planned_runs": planned,
        "execution_successes": succeeded,
        "execution_success_rate": {"numerator": succeeded, "denominator": planned},
        "execution_attempts": len(attempts),
        "failed_attempts": sum(a.status == "failed" for a in attempts),
        "unknown_attempts": sum(a.status == "unknown" for a in attempts),
        "cancelled_runs": sum(r.status == "cancelled" for r in runs),
        "scorers": scorer_summaries,
    }


def run_details(session: Session, experiment: Experiment, limit: int, offset: int):
    runs = session.scalars(
        select(CaseRun)
        .where(CaseRun.experiment_id == experiment.id)
        .order_by(CaseRun.created_at, CaseRun.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [run_detail(session, run) for run in runs]


def run_detail(session: Session, run: CaseRun):
    attempts = session.scalars(
        select(Attempt)
        .where(Attempt.case_run_id == run.id)
        .order_by(Attempt.created_at, Attempt.id)
    ).all()
    item = public_record(run)
    item["case"] = public_record(session.get(CaseVersion, run.case_version_id))
    item["attempts"] = []
    for attempt in attempts:
        data = public_record(attempt)
        data["score_runs"] = [
            public_record(s)
            for s in session.scalars(
                select(ScoreRun)
                .where(ScoreRun.attempt_id == attempt.id)
                .order_by(ScoreRun.created_at, ScoreRun.id)
            )
        ]
        data["manifests"] = [
            public_record(m)
            for m in session.scalars(
                select(Manifest).where(Manifest.attempt_id == attempt.id).order_by(Manifest.version)
            )
        ]
        item["attempts"].append(data)
    return item
