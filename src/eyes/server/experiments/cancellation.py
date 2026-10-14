"""Append-only cancellation intent and platform handling, never stop evidence."""

from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from eyes.server.domain import DomainError, digest, public_record, scoped
from eyes.server.experiments import batches
from eyes.server.scheduling import service as scheduling
from eyes.server.storage.database import scheduling_lock
from eyes.server.storage.models import (
    Attempt,
    CancellationAudit,
    CaseRun,
    Credential,
    EvidenceWait,
    Experiment,
    ExperimentBatch,
    ScoreRun,
    WorkItem,
    now,
)


def snapshot(session, experiment):
    session.flush()
    result = {"status": experiment.status}
    for name, _model, predicate, column in (
        ("case_runs", CaseRun, CaseRun.experiment_id == experiment.id, CaseRun.status),
        ("work", WorkItem, WorkItem.experiment_id == experiment.id, WorkItem.status),
        (
            "attempts",
            Attempt,
            Attempt.case_run_id.in_(
                select(CaseRun.id).where(CaseRun.experiment_id == experiment.id)
            ),
            Attempt.status,
        ),
        (
            "scores",
            ScoreRun,
            ScoreRun.attempt_id.in_(
                select(Attempt.id).join(CaseRun).where(CaseRun.experiment_id == experiment.id)
            ),
            ScoreRun.status,
        ),
        (
            "waits",
            EvidenceWait,
            EvidenceWait.attempt_id.in_(
                select(Attempt.id).join(CaseRun).where(CaseRun.experiment_id == experiment.id)
            ),
            EvidenceWait.status,
        ),
    ):
        result[name] = dict(
            session.execute(select(column, func.count()).where(predicate).group_by(column)).all()
        )
    result["reserved"] = session.scalar(
        select(func.count())
        .select_from(WorkItem)
        .where(WorkItem.experiment_id == experiment.id, WorkItem.reserved.is_(True))
    )
    result["score_stop_requests"] = session.scalar(
        select(func.count())
        .select_from(ScoreRun)
        .join(Attempt)
        .join(CaseRun)
        .where(CaseRun.experiment_id == experiment.id, ScoreRun.cancel_requested_at.is_not(None))
    )
    return result


def handle_member(session, actor, object_id, reason, parent_id=None, **transport):
    before = None
    try:
        with session.begin_nested():
            experiment = scoped(session, Experiment, object_id, actor.project_id, lock=True)
            before = snapshot(session, experiment)
            scheduling._cancel(session, actor.project_id, object_id)
            after = snapshot(session, experiment)
        outcome = (
            "already_finished"
            if before["status"] in batches.TERMINAL
            else "processed"
            if before != after
            else "no_change"
        )
        result = {"before": before, "after": after}
        status = 200
    except DomainError as error:
        outcome, status = "failed", error.status
        result = {"error_code": error.code, "before": before}
    audit = CancellationAudit(
        project_id=actor.project_id,
        actor_id=actor.id,
        actor_role=actor.role,
        object_kind="experiment",
        object_id=object_id,
        parent_id=parent_id,
        reason=reason,
        outcome=outcome,
        http_status=status,
        result=result,
        **transport,
    )
    session.add(audit)
    session.flush()
    return audit


def request(session: Session, actor: Credential, kind: str, object_id: UUID, reason, key):
    if actor.role != "manage":
        raise DomainError(403, "permission_denied", "manage credential required")
    requested_at = now()
    scheduling_lock(session)
    # Hash transport keys: callers must use opaque keys, never secrets.
    key_digest = digest(key) if key is not None else None
    request_digest = digest({"kind": kind, "id": str(object_id), "reason": reason})
    if key_digest:
        previous = session.scalar(
            select(CancellationAudit).where(
                CancellationAudit.project_id == actor.project_id,
                CancellationAudit.actor_id == actor.id,
                CancellationAudit.key_digest == key_digest,
            )
        )
        if previous:
            if previous.request_digest != request_digest:
                raise DomainError(409, "idempotency_conflict", "same key has different parameters")
            return previous, True
    if kind == "experiment":
        audit = handle_member(
            session,
            actor,
            object_id,
            reason,
            created_at=requested_at,
            key_digest=key_digest,
            request_digest=request_digest,
        )
    else:
        audit = CancellationAudit(
            id=uuid4(),
            created_at=requested_at,
            project_id=actor.project_id,
            actor_id=actor.id,
            actor_role=actor.role,
            object_kind="batch",
            object_id=object_id,
            reason=reason,
            outcome="processed",
            http_status=200,
            result={},
            key_digest=key_digest,
            request_digest=request_digest,
        )
        try:
            batch = scoped(session, ExperimentBatch, object_id, actor.project_id)
            ids = session.scalars(
                select(Experiment.id).where(Experiment.batch_id == batch.id).order_by(Experiment.id)
            ).all()
            members = [handle_member(session, actor, id, reason, audit.id) for id in ids]
            counts = {
                outcome: sum(m.outcome == outcome for m in members)
                for outcome in {m.outcome for m in members}
            }
            audit.outcome = (
                "partial_failure"
                if counts.get("failed")
                else "processed"
                if counts.get("processed")
                else "already_finished"
                if counts.get("already_finished") == len(members)
                else "no_change"
            )
            audit.result = {"members": counts, "member_count": len(members)}
        except DomainError as error:
            audit.outcome, audit.http_status = "failed", error.status
            audit.result = {"error_code": error.code}
        session.add(audit)
    session.flush()
    return audit, False


def view(audit):
    return {
        key: value
        for key, value in public_record(audit).items()
        if key not in {"key_digest", "request_digest"}
    }


def listing(session, project_id, limit, offset, kind=None, object_id=None, parent_id=None):
    query = select(CancellationAudit).where(CancellationAudit.project_id == project_id)
    if kind:
        query = query.where(CancellationAudit.object_kind == kind)
    if object_id:
        query = query.where(CancellationAudit.object_id == object_id)
    if parent_id:
        query = query.where(CancellationAudit.parent_id == parent_id)
    return [
        view(row)
        for row in session.scalars(
            query.order_by(CancellationAudit.created_at.desc(), CancellationAudit.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ]
