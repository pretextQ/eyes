"""Project-scoped, bounded observation content expiration (not a storage quota)."""

from datetime import timedelta

from sqlalchemy import or_, select, text

from eyes.server.observation.service import summary
from eyes.server.storage.database import maintenance_lock
from eyes.server.storage.models import ObservedEvent, ObservedRun, Project, now

TERMINAL = ("completed", "failed", "cancelled", "limited")


def maintain_observations(sessions, settings, *, apply=False, project_id=None):
    project_id = project_id or settings.observation_retention_project_id
    days = settings.observation_retention_days
    result = {
        "mode": "apply" if apply else "preview",
        "project_id": str(project_id) if project_id else None,
        "retention_days": days,
        "run_batch_limit": settings.observation_retention_run_batch,
        "event_batch_limit": settings.observation_retention_event_batch,
        "max_batches": settings.observation_retention_max_batches,
        "runs": [],
        "events": 0,
        "batches": 0,
        "batch_limit_reached": False,
    }
    if project_id is None:
        if days:
            raise ValueError(
                "observation retention requires --project-id or configured project UUID"
            )
        return result
    cutoff = now() - timedelta(days=days)
    for _ in range(settings.observation_retention_max_batches if apply else 1):
        # A commit per bounded batch, shared backup lock and no scheduler/global
        # exclusive lock. Run locks serialize expiration with source ingestion.
        with sessions() as session, session.begin():
            session.execute(text("SET LOCAL lock_timeout = '2s'"))
            session.execute(text("SET LOCAL statement_timeout = '15s'"))
            maintenance_lock(session)
            if session.get(Project, project_id) is None:
                raise ValueError("observation retention project does not exist")
            runs = []
            if days:
                query = (
                    select(ObservedRun)
                    .where(
                        ObservedRun.project_id == project_id,
                        ObservedRun.expired_at.is_(None),
                        ObservedRun.status.in_(TERMINAL),
                        ObservedRun.terminal_sequence.is_not(None),
                        ObservedRun.terminal_received_at < cutoff,
                        ObservedRun.last_seen_at < cutoff,
                    )
                    .order_by(ObservedRun.terminal_received_at, ObservedRun.id)
                    .limit(settings.observation_retention_run_batch)
                )
                if apply:
                    query = query.with_for_update(skip_locked=True)
                runs = session.scalars(query).all()
            current = now()
            if apply:
                for run in runs:
                    run.expiration_summary = {
                        "reason": "retention",
                        "retention_days": days,
                        "cutoff": cutoff.isoformat(),
                        "terminal_received_at": run.terminal_received_at.isoformat(),
                        "last_seen_at": run.last_seen_at.isoformat(),
                        "previous_evidence_status": summary(run)["evidence_status"],
                        "events": run.metrics.get("events", 0),
                    }
                    run.expired_at = current
                    run.prompt = None
                session.flush()
            query = (
                select(ObservedEvent)
                .join(ObservedRun, ObservedRun.id == ObservedEvent.run_id)
                .where(
                    ObservedEvent.project_id == project_id,
                    ObservedRun.project_id == project_id,
                    ObservedEvent.expired_at.is_(None),
                    or_(
                        ObservedRun.expired_at.is_not(None),
                        ObservedRun.id.in_([run.id for run in runs]) if not apply else False,
                    ),
                )
                .order_by(ObservedEvent.run_id, ObservedEvent.id)
                .limit(settings.observation_retention_event_batch)
            )
            if apply:
                query = query.with_for_update(of=ObservedEvent, skip_locked=True)
            events = session.scalars(query).all()
            if apply:
                for event in events:
                    # Identity, sequence, original digest and server receipt remain
                    # audit metadata, never presented as readable original evidence.
                    event.content = {}
                    event.expired_at = current
            result["runs"].extend(str(run.id) for run in runs)
            result["events"] += len(events)
            result["batches"] += 1
            result["batch_limit_reached"] = (
                len(runs) == settings.observation_retention_run_batch
                or len(events) == settings.observation_retention_event_batch
            )
        if not runs and not events:
            break
    return result
