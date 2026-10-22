from uuid import UUID

from sqlalchemy import Text, cast, func, select
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
    if target.content["capabilities"]["adapter"] == "agent_http":
        discovery = target.content["config"]["discovery"]
        if (
            any(case.content["artifact_requirements"] for case in cases)
            and not discovery["artifacts"]
        ):
            raise DomainError(422, "agent_artifacts", "Agent cannot provide required artifacts")
        if any(case.content["environment"] for case in cases):
            raise DomainError(
                422, "agent_environment", "v1 business setup must be encoded in input"
            )
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
    run_counts = dict(
        session.execute(
            select(CaseRun.status, func.count())
            .where(CaseRun.experiment_id == experiment.id)
            .group_by(CaseRun.status)
        ).all()
    )
    attempt_counts = dict(
        session.execute(
            select(Attempt.status, func.count())
            .join(CaseRun)
            .where(CaseRun.experiment_id == experiment.id)
            .group_by(Attempt.status)
        ).all()
    )
    ranked_attempts = (
        select(
            Attempt.id,
            func.row_number()
            .over(partition_by=Attempt.case_run_id, order_by=(Attempt.created_at, Attempt.id))
            .label("position"),
        )
        .join(CaseRun)
        .where(CaseRun.experiment_id == experiment.id, Attempt.status == "succeeded")
    ).subquery()
    selected_ids = select(ranked_attempts.c.id).where(ranked_attempts.c.position == 1)
    planned = sum(run_counts.values())
    succeeded = session.scalar(select(func.count()).select_from(selected_ids.subquery()))
    ranked_scores = (
        select(
            ScoreRun.scorer_id,
            ScoreRun.status,
            ScoreRun.result["verdict"].as_string().label("verdict"),
            func.row_number()
            .over(
                partition_by=(ScoreRun.attempt_id, ScoreRun.scorer_id),
                order_by=(ScoreRun.created_at, ScoreRun.id),
            )
            .label("position"),
        ).where(ScoreRun.attempt_id.in_(selected_ids))
    ).subquery()
    valid = (ranked_scores.c.status == "completed") & ranked_scores.c.verdict.in_(["pass", "fail"])
    counts = {
        str(row.scorer_id): (row.valid, row.passed, row.na)
        for row in session.execute(
            select(
                ranked_scores.c.scorer_id,
                func.count().filter(valid).label("valid"),
                func.count().filter(valid & (ranked_scores.c.verdict == "pass")).label("passed"),
                func.count().filter(ranked_scores.c.verdict == "not_applicable").label("na"),
            )
            .where(ranked_scores.c.position == 1)
            .group_by(ranked_scores.c.scorer_id)
        )
    }
    scorer_summaries = []
    for scorer in experiment.snapshot["scorers"]:
        # Stable first published score per selected attempt. Re-scoring history is
        # exposed separately; it cannot silently replace the original aggregate.
        valid_count, passed, na = counts.get(scorer["id"], (0, 0, 0))
        scorer_summaries.append(
            {
                "scorer_version_id": scorer["id"],
                "planned_runs": planned,
                "valid_scores": valid_count,
                "passed": passed,
                "not_applicable": na,
                "unresolved": max(0, planned - valid_count - na),
                "score_coverage": {"numerator": valid_count, "denominator": planned},
                "valid_score_pass_rate": {"numerator": passed, "denominator": valid_count},
            }
        )
    return {
        "schema_version": "1.0",
        "experiment_id": str(experiment.id),
        "status": experiment.status,
        "planned_runs": planned,
        "execution_successes": succeeded,
        "execution_success_rate": {"numerator": succeeded, "denominator": planned},
        "execution_attempts": sum(attempt_counts.values()),
        "failed_attempts": attempt_counts.get("failed", 0),
        "unknown_attempts": attempt_counts.get("unknown", 0),
        "cancelled_runs": run_counts.get("cancelled", 0),
        "scorers": scorer_summaries,
    }


def detail_budget(session, run_ids, *, include_history=True):
    total = 0
    statements = [
        select(func.count(CaseRun.id), func.sum(func.octet_length(cast(CaseVersion.content, Text))))
        .join(CaseVersion, CaseRun.case_version_id == CaseVersion.id)
        .where(CaseRun.id.in_(run_ids)),
        select(
            func.count(Attempt.id), func.sum(func.octet_length(cast(Attempt.result, Text)))
        ).where(Attempt.case_run_id.in_(run_ids)),
    ]
    if include_history:
        for model, column in ((ScoreRun, ScoreRun.result), (Manifest, Manifest.content)):
            statements.append(
                select(func.count(model.id), func.sum(func.octet_length(cast(column, Text))))
                .join(Attempt)
                .where(Attempt.case_run_id.in_(run_ids))
            )
    for statement in statements:
        count, size = session.execute(statement).one()
        total += count * 1024 + (size or 0)
        if total > 16 * 1024 * 1024:
            raise DomainError(
                413, "detail_too_large", "reduce page size or use paginated attempt history"
            )


def run_details(
    session: Session, experiment: Experiment, limit: int, offset: int, *, include_history=True
):
    runs = session.scalars(
        select(CaseRun)
        .where(CaseRun.experiment_id == experiment.id)
        .order_by(CaseRun.created_at, CaseRun.id)
        .limit(limit)
        .offset(offset)
    ).all()
    detail_budget(session, [run.id for run in runs], include_history=include_history)
    return [run_detail(session, run, checked=True, include_history=include_history) for run in runs]


def run_detail(session: Session, run: CaseRun, *, checked=False, include_history=True):
    if not checked:
        detail_budget(session, [run.id], include_history=include_history)
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
        if not include_history:
            item["attempts"].append(data)
            continue
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
