"""Supplement original terminal operations. No execution leases or automatic rescore."""

import hashlib
import logging
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select

from eyes.contracts.agent_protocol import AgentRun
from eyes.contracts.base import explicit_versions
from eyes.contracts.evidence import ArtifactMetadata, ExecutionEvent
from eyes.contracts.target import TargetPublish
from eyes.server.domain import DomainError, digest, scoped
from eyes.server.evidence import service as evidence
from eyes.server.scheduling import service
from eyes.server.storage.database import scheduling_lock
from eyes.server.storage.models import (
    Artifact,
    Attempt,
    CaseRun,
    CaseVersion,
    Event,
    ResolutionRecord,
    TargetVersion,
    WorkItem,
    now,
)


def save(work, state):
    work.reconciliation = {**work.reconciliation, "evidence_recovery": state}


def renew(state):
    expires = now() + timedelta(seconds=180)
    delay = min(3600, 15 * 2 ** min(state["count"] - 1, 8))
    return {
        **state,
        "expires_at": expires.isoformat(),
        "due_at": (expires + timedelta(seconds=delay)).isoformat(),
    }


def claim(session, credential, request):
    scheduling_lock(session)
    runner = service.authorized_runner(session, credential, request.runner_id)
    if "execute" not in credential.work_kinds:
        raise DomainError(403, "work_kind", "execution scope required")
    query = (
        select(WorkItem)
        .join(Attempt, WorkItem.attempt_id == Attempt.id)
        .where(
            WorkItem.project_id == credential.project_id,
            WorkItem.kind == "execute",
            WorkItem.plugin == "agent_http",
            WorkItem.status == "completed",
            WorkItem.reserved.is_(False),
            Attempt.result["source"].as_string() == "automatic_agent_http_query",
        )
    )
    if credential.target_ids:
        query = query.where(WorkItem.target_id.in_([UUID(t) for t in credential.target_ids]))
    for work in session.scalars(
        query.order_by(WorkItem.created_at).with_for_update(skip_locked=True, of=WorkItem)
    ):
        attempt = session.get(Attempt, work.attempt_id)
        state = work.reconciliation.get("evidence_recovery", {})
        if attempt.evidence_expired_at or state.get("done"):
            continue
        if state.get("due_at") and datetime.fromisoformat(state["due_at"]) > now():
            continue
        # Historical terminal resolutions are eligible without rewriting their records.
        original = next(
            (
                r.content["snapshot"]
                for r in session.scalars(
                    select(ResolutionRecord)
                    .where(ResolutionRecord.attempt_id == attempt.id)
                    .order_by(ResolutionRecord.created_at.desc())
                )
                if r.content.get("applied") and r.content.get("snapshot")
            ),
            None,
        )
        if original is None or attempt.status != original["status"]:
            continue
        target = session.get(TargetVersion, work.target_id).content
        if "agent_http" not in runner.capabilities.get(
            "adapters", []
        ) or not service.supports_target(runner.capabilities, target):
            continue
        token = uuid4()
        count = state.get("count", 0) + 1
        expires = now() + timedelta(seconds=180)
        save(
            work,
            {
                **state,
                "token": str(token),
                "credential_id": str(credential.id),
                "runner_id": str(runner.id),
                "expires_at": expires.isoformat(),
                "due_at": (
                    expires + timedelta(seconds=min(3600, 15 * 2 ** min(count - 1, 8)))
                ).isoformat(),
                "count": count,
                "original": original,
                "verified": False,
            },
        )
        session.add(
            ResolutionRecord(
                attempt_id=attempt.id,
                credential_id=credential.id,
                previous_status=attempt.status,
                content={
                    "source": "agent_http_evidence_recovery",
                    "phase": "claimed",
                    "query_id": str(token),
                    "runner_id": str(runner.id),
                },
            )
        )
        return {
            "schema_version": "1.0",
            "work_item_id": work.id,
            "attempt_id": attempt.id,
            "case_run_id": work.case_run_id,
            "lease_token": token,
            "lease_expires_at": expires,
            "idempotency_key": attempt.idempotency_key,
            "remote_operation_id": attempt.remote_operation_id,
            "target": explicit_versions(TargetPublish, target, source="recovery_target"),
            "phase": "evidence",
            "recovery_cursor": state.get("cursor"),
            "recovery_events_done": state.get("events_done", False),
        }
    return None


def authorize(session, credential, work_id, token, *, verified=True):
    scheduling_lock(session)
    work = scoped(session, WorkItem, work_id, credential.project_id, lock=True)
    service.authorize_work(credential, work)
    state = work.reconciliation.get("evidence_recovery", {})
    if (
        work.kind != "execute"
        or work.plugin != "agent_http"
        or work.status != "completed"
        or work.reserved
        or "execute" not in credential.work_kinds
        or state.get("token") != str(token)
        or state.get("credential_id") != str(credential.id)
        or datetime.fromisoformat(state["expires_at"]) <= now()
        or (verified and not state.get("verified"))
    ):
        raise DomainError(409, "stale_recovery", "no verified recovery lease for this operation")
    attempt = session.get(Attempt, work.attempt_id)
    if attempt.evidence_expired_at:
        raise DomainError(410, "evidence_expired", "expired evidence cannot be recovered")
    return work, attempt, state


def observe(session, credential, work_id, request):
    work, attempt, state = authorize(
        session, credential, work_id, request.lease_token, verified=False
    )
    service.authorized_runner(session, credential, request.runner_id)
    snapshot = request.snapshot
    original = AgentRun.model_validate(state["original"])
    valid = (
        str(request.runner_id) == state["runner_id"]
        and snapshot is not None
        and request.diagnostic == "snapshot_received"
        and snapshot.task_id == work.case_run_id
        and snapshot.attempt_id == attempt.id
        and str(snapshot.run_id) == attempt.remote_operation_id
        and snapshot.run_id == original.run_id
        and snapshot.revision >= original.revision
        and snapshot.result == original.result
        and snapshot.status == attempt.status
    )
    fingerprint = digest(request.model_dump(mode="json"))
    if (valid and state.get("verified")) or state.get("observation_digest") == fingerprint:
        return {
            "schema_version": "1.0",
            "verified": valid,
            "cursor": state.get("cursor"),
            "events_done": state.get("events_done", False),
            "artifacts": state.get("artifacts", []),
        }
    session.add(
        ResolutionRecord(
            attempt_id=attempt.id,
            credential_id=credential.id,
            previous_status=attempt.status,
            content={
                "source": "agent_http_evidence_recovery",
                "phase": "observed",
                "query_id": str(request.lease_token),
                "verified": valid,
                "diagnostic": "original_result_confirmed"
                if valid
                else "identity_or_result_mismatch",
                "snapshot": evidence.redact(snapshot.model_dump(mode="json")) if snapshot else None,
            },
        )
    )
    save(work, {**state, "verified": valid, "observation_digest": fingerprint})
    return {
        "schema_version": "1.0",
        "verified": valid,
        "cursor": state.get("cursor"),
        "events_done": state.get("events_done", False),
        "artifacts": state.get("artifacts", []),
    }


def events(session, credential, work_id, request):
    work, attempt, state = authorize(session, credential, work_id, request.lease_token)
    if str(request.runner_id) != state["runner_id"]:
        raise DomainError(403, "runner_scope", "recovery belongs to another Runner")
    page = request.page
    original = AgentRun.model_validate(state["original"])
    discovery = session.get(TargetVersion, work.target_id).content["config"]["discovery"]
    if not discovery["events"] or page.run_id != original.run_id:
        raise DomainError(
            409, "identity_mismatch", "event page does not belong to declared operation"
        )
    key = digest(request.cursor)
    fingerprint = digest(page.model_dump(mode="json"))
    receipts = state.get("pages", {})
    if key in receipts:
        if receipts[key] != fingerprint:
            raise DomainError(409, "event_conflict", "cursor returned different evidence")
        return {"schema_version": "1.0", "duplicate": True}
    if state.get("events_done") or request.cursor != state.get("cursor"):
        raise DomainError(409, "cursor_conflict", "page is not the next durable cursor")
    if len(receipts) >= 1000 or (
        page.next_cursor is not None and (not page.items or page.next_cursor == request.cursor)
    ):
        raise DomainError(422, "capture_limit", "event drain cannot advance within bounds")
    if (
        page.items
        and state.get("last_sequence") is not None
        and page.items[0].sequence <= state["last_sequence"]
    ):
        raise DomainError(409, "sequence_conflict", "event pages are not in stream order")
    records = session.scalars(select(Event).where(Event.attempt_id == attempt.id)).all()
    native = {}
    sequences = {}
    for record in records:
        value = record.content
        if value.get("type") == "agent.event" and value.get("data", {}).get("run_id") == str(
            original.run_id
        ):
            child = value["data"]
            eid = child["event_id"]
            if eid in native and digest(native[eid]) != digest(child):
                raise DomainError(409, "event_conflict", "existing native event conflicts")
            native[eid] = child
            if child["sequence"] in sequences and sequences[child["sequence"]] != eid:
                raise DomainError(409, "sequence_conflict", "existing native sequence conflicts")
            sequences[child["sequence"]] = eid
    changed = False
    for event in page.items:
        value = evidence.redact(event.model_dump(mode="json"))
        eid = str(event.event_id)
        if eid in native:
            if digest(native[eid]) != digest(value):
                logging.getLogger(__name__).warning(
                    "recovery_event_conflict attempt=%s event=%s", attempt.id, eid
                )
                raise DomainError(409, "event_conflict", "native event has different content")
            continue
        if event.sequence in sequences or len(native) >= 10000:
            raise DomainError(409, "sequence_conflict", "sequence collision or capture limit")
        envelope = ExecutionEvent(
            schema_version="1.0",
            event_id=event.event_id,
            producer_id=f"agent_http:{work.target_id}:{original.run_id}",
            attempt_id=attempt.id,
            trace_id=attempt.trace_id,
            span_id=attempt.root_span_id,
            sequence=event.sequence,
            occurred_at=event.occurred_at,
            type="agent.event",
            source="target_trace",
            data=value,
        )
        content = envelope.model_dump(mode="json")
        session.add(
            Event(
                project_id=work.project_id,
                attempt_id=attempt.id,
                producer_id=envelope.producer_id,
                event_id=envelope.event_id,
                digest=digest(content),
                content=content,
            )
        )
        native[eid], sequences[event.sequence] = value, eid
        changed = True
    save(
        work,
        renew(
            {
                **state,
                "pages": {**receipts, key: fingerprint},
                "cursor": page.next_cursor,
                "events_done": page.next_cursor is None,
                "event_evidence": page.evidence.model_dump(mode="json"),
                "last_sequence": page.items[-1].sequence
                if page.items
                else state.get("last_sequence"),
                "event_capture_partial": state.get("event_capture_partial", False)
                or page.evidence.status != "sealed"
                or page.evidence.dropped_events != 0,
            }
        ),
    )
    session.flush()
    if changed:
        evidence.seal(session, attempt)
    return {"schema_version": "1.0", "duplicate": False}


def artifact(session, credential, work_id, token, artifact_id, content, store, max_bytes):
    work, attempt, state = authorize(session, credential, work_id, token)
    discovery = session.get(TargetVersion, work.target_id).content["config"]["discovery"]
    original = AgentRun.model_validate(state["original"])
    item = next((a for a in original.result.artifacts if a.artifact_id == artifact_id), None)
    if item is None or not discovery["artifacts"]:
        raise DomainError(409, "artifact_scope", "artifact not declared by original operation")
    metadata = ArtifactMetadata(
        schema_version="1.0",
        name=item.name,
        media_type=item.media_type,
        size=item.size_bytes,
        sha256=item.sha256,
    )
    record = evidence.initiate_artifact(
        session, credential, attempt.id, metadata, max_bytes, recovery_token=token
    )
    evidence.publish_artifact(session, credential, record.id, content, store, recovery_token=token)
    # An old ready registration alone does not prove its retained bytes survived.
    # Restore only the verified original bytes under the existing controlled key.
    path = store.path(record.storage_key)
    if (
        not path.is_file()
        or path.stat().st_size != item.size_bytes
        or hashlib.sha256(path.read_bytes()).hexdigest() != item.sha256
    ):
        store.publish(record.storage_key, content)
    save(
        work,
        renew(
            {
                **state,
                "artifacts": sorted(set(state.get("artifacts", [])) | {str(artifact_id)}),
            }
        ),
    )
    return {"schema_version": "1.0", "id": record.id}


def close(session, credential, work_id, request):
    work, attempt, state = authorize(session, credential, work_id, request.lease_token)
    if str(request.runner_id) != state["runner_id"]:
        raise DomainError(403, "runner_scope", "recovery belongs to another Runner")
    if state.get("done"):
        return {"schema_version": "1.0", "duplicate": True, "manifest_id": state["manifest_id"]}
    original = AgentRun.model_validate(state["original"])
    discovery = session.get(TargetVersion, work.target_id).content["config"]["discovery"]
    if discovery["events"] and not state.get("events_done"):
        raise DomainError(409, "events_pending", "remote event stream has not been drained")
    required = {str(a.artifact_id) for a in original.result.artifacts}
    if required - set(state.get("artifacts", [])):
        raise DomainError(409, "artifacts_pending", "original artifacts have not been published")
    gaps = []
    if not discovery["events"]:
        gaps.append("target does not support events")
    if not discovery["artifacts"]:
        gaps.append("target does not support artifacts")
    case_run = session.get(CaseRun, work.case_run_id)
    case = session.get(CaseVersion, case_run.case_version_id).content
    names = {a.name for a in original.result.artifacts}
    gaps.extend(
        "required artifact missing: " + name
        for name in case.get("artifact_requirements", [])
        if name not in names
    )
    if session.scalar(
        select(Artifact.id)
        .where(Artifact.attempt_id == attempt.id, Artifact.status == "pending")
        .limit(1)
    ):
        gaps.append("Eyes artifact upload still pending")
    remote = original.result.evidence
    page = state.get("event_evidence", {})
    sealed = (
        not gaps
        and remote.status == "sealed"
        and remote.dropped_events == 0
        and page.get("status") == "sealed"
        and page.get("dropped_events") == 0
        and not state.get("event_capture_partial")
    )
    attempt.evidence_status = "sealed" if sealed else "partial"
    # AgentResult cleanup is an explicit fact from the authenticated original run.
    # Unknown never becomes success merely because execution has succeeded.
    if original.result.cleanup_status != "unknown":
        attempt.cleanup_status = original.result.cleanup_status
    attempt.result = {
        **attempt.result,
        "evidence_status": attempt.evidence_status,
        "dropped_events": remote.dropped_events,
        "cleanup_status": attempt.cleanup_status,
        "evidence_details": {
            "source": "agent_http_evidence_recovery",
            "run_id": str(original.run_id),
            "revision": original.revision,
            "agent_evidence": remote.model_dump(mode="json"),
            "event_evidence": page,
            "transfer_gaps": gaps,
        },
    }
    manifest = evidence.seal(session, attempt)
    save(work, {**state, "done": True, "manifest_id": str(manifest.id)})
    session.add(
        ResolutionRecord(
            attempt_id=attempt.id,
            credential_id=credential.id,
            previous_status=attempt.status,
            content={
                "source": "agent_http_evidence_recovery",
                "phase": "closed",
                "query_id": str(request.lease_token),
                "manifest_id": str(manifest.id),
                "cleanup_status": attempt.cleanup_status,
                "evidence_status": attempt.evidence_status,
            },
        )
    )
    return {"schema_version": "1.0", "duplicate": False, "manifest_id": manifest.id}
