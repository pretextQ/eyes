import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select

from eyes.runner.files import redact
from eyes.server.domain import DomainError, digest, public_record
from eyes.server.storage.models import ObservationSource, ObservedEvent, ObservedRun


def create_source(session, project_id, body):
    token = "eyes_obs_" + secrets.token_urlsafe(32)
    source = ObservationSource(
        project_id=project_id,
        name=body.name,
        token_digest=hashlib.sha256(token.encode()).hexdigest(),
    )
    session.add(source)
    session.flush()
    return {**public_record(source), "token": token}


def summary(run):
    metrics = run.metrics
    expected = run.terminal_sequence or metrics.get("last_sequence", 0)
    gaps = max(0, expected - metrics.get("events", 0))
    complete = (
        run.terminal_sequence is not None
        and metrics.get("has_start", False)
        and gaps == 0
        and metrics.get("dropped", 0) == 0
        and metrics.get("truncated", 0) == 0
    )
    stale = run.status == "running" and run.last_seen_at < datetime.now(UTC) - timedelta(seconds=30)
    return {
        **public_record(run),
        "status": "disconnected" if stale else run.status,
        "evidence_status": "complete"
        if complete
        else "partial"
        if (
            run.terminal_sequence is not None
            or stale
            or gaps
            or not metrics.get("has_start", False)
            or metrics.get("truncated", 0)
            or metrics.get("dropped", 0)
        )
        else "collecting",
        "sequence_gaps": gaps,
    }


def add_metrics(run, event):
    metrics = dict(run.metrics or {})
    metrics["events"] = metrics.get("events", 0) + 1
    metrics["last_sequence"] = max(metrics.get("last_sequence", 0), event.sequence)
    metrics["truncated"] = metrics.get("truncated", 0) + int(event.truncated)
    counters = {"turn_start": "turns", "model_start": "model_calls", "tool_start": "tool_calls"}
    if event.type in counters:
        key = counters[event.type]
        metrics[key] = metrics.get(key, 0) + 1
    if event.type == "run_start":
        metrics["has_start"] = True
        metrics["started_at"] = event.occurred_at.isoformat()
        run.prompt = str(event.data.get("prompt", ""))[:4000] if run.capture_body else None
    elif event.type == "run_end":
        run.status = event.data["status"]
        run.terminal_sequence = event.sequence
        metrics["ended_at"] = event.occurred_at.isoformat()
        metrics["dropped"] = event.data["dropped_events"]
    elif event.type == "model_end":
        usage = event.data.get("usage")
        if isinstance(usage, dict) and all(
            type(usage.get(k)) is int and usage[k] >= 0
            for k in ("input_tokens", "output_tokens", "total_tokens")
        ):
            metrics["usage_responses"] = metrics.get("usage_responses", 0) + 1
            for key in ("input_tokens", "output_tokens", "total_tokens"):
                metrics[key] = metrics.get(key, 0) + usage[key]
        else:
            metrics["unknown_usage"] = metrics.get("unknown_usage", 0) + 1
    run.metrics = metrics


def ingest(session, source, body, supplied_token):
    # One source lock serializes retries and concurrent producers without a global scheduler lock.
    source = session.scalar(
        select(ObservationSource)
        .where(ObservationSource.id == source.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if source.revoked:
        raise DomainError(401, "invalid_token", "observation token was revoked")
    run = session.scalar(
        select(ObservedRun).where(
            ObservedRun.source_id == source.id, ObservedRun.external_id == body.run_id
        )
    )
    metadata = {key: getattr(body, key) for key in ("session_id", "agent", "model", "capture_body")}
    if run is None:
        run = ObservedRun(
            project_id=source.project_id, source_id=source.id, external_id=body.run_id, **metadata
        )
        session.add(run)
        session.flush()
    elif any(getattr(run, key) != value for key, value in metadata.items()):
        raise DomainError(409, "run_identity_conflict", "run metadata is immutable")
    accepted = []
    for event in sorted(body.events, key=lambda value: value.sequence):
        payload = event.model_dump(mode="json")
        # Producer masks its model key; server also masks the supplied observation credential.
        payload["data"] = redact(payload["data"], [supplied_token])
        if len(json.dumps(payload, ensure_ascii=False).encode()) > 65536:
            raise DomainError(413, "event_too_large", "observation event exceeds 64 KiB")
        content_digest = digest(payload)
        existing = session.scalars(
            select(ObservedEvent).where(
                ObservedEvent.source_id == source.id,
                or_(
                    ObservedEvent.event_id == event.event_id,
                    (ObservedEvent.run_id == run.id) & (ObservedEvent.sequence == event.sequence),
                ),
            )
        ).all()
        if existing:
            if (
                len(existing) != 1
                or existing[0].run_id != run.id
                or existing[0].digest != content_digest
            ):
                raise DomainError(409, "event_conflict", "event identity has different content")
        else:
            if run.terminal_sequence is not None and (
                event.sequence > run.terminal_sequence or event.type == "run_end"
            ):
                raise DomainError(
                    409, "run_closed", "event is beyond the recorded terminal boundary"
                )
            if event.type == "run_end" and event.sequence < (run.metrics or {}).get(
                "last_sequence", 0
            ):
                raise DomainError(
                    409, "terminal_conflict", "terminal event precedes collected events"
                )
            session.add(
                ObservedEvent(
                    project_id=source.project_id,
                    source_id=source.id,
                    run_id=run.id,
                    event_id=event.event_id,
                    sequence=event.sequence,
                    content=payload,
                    digest=content_digest,
                )
            )
            # Derive display fields only from the sanitized persisted content.
            add_metrics(run, event.model_copy(update={"data": payload["data"]}))
        accepted.append(str(event.event_id))
    source.last_seen_at = run.last_seen_at = datetime.now(UTC)
    session.flush()
    return {"schema_version": "1.0", "run_id": str(run.id), "accepted": accepted}
