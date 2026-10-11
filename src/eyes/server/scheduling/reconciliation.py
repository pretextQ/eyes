"""Read-only recovery coordination; never grants a business execution lease."""

from datetime import datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import select

from eyes.contracts.agent_protocol import TERMINAL_STATES
from eyes.contracts.base import explicit_versions
from eyes.contracts.target import Resolution, TargetPublish
from eyes.server.domain import DomainError, digest, scoped
from eyes.server.evidence.service import redact
from eyes.server.scheduling import service
from eyes.server.storage.database import scheduling_lock
from eyes.server.storage.models import Attempt, ResolutionRecord, TargetVersion, WorkItem, now


def claim_record_id(token):
    return uuid5(NAMESPACE_URL, f"eyes:reconciliation:{token}:claim")


def claim(session, credential, request):
    scheduling_lock(session)
    runner = service.authorized_runner(session, credential, request.runner_id)
    if "execute" not in credential.work_kinds:
        raise DomainError(403, "work_kind", "execution scope is required for reconciliation")
    current = now()
    query = select(WorkItem).where(
        WorkItem.project_id == credential.project_id,
        WorkItem.kind == "execute",
        WorkItem.plugin == "agent_http",
        WorkItem.status == "unknown",
        WorkItem.reserved.is_(True),
    )
    if credential.target_ids:
        query = query.where(WorkItem.target_id.in_([UUID(tid) for tid in credential.target_ids]))
    with session.scalars(
        query.order_by(WorkItem.created_at, WorkItem.id)
        .with_for_update(skip_locked=True)
        .execution_options(yield_per=100)
    ) as works:
        for work in works:
            state = work.reconciliation
            if state.get("due_at") and datetime.fromisoformat(state["due_at"]) > current:
                continue
            target = session.get(TargetVersion, work.target_id).content
            if (
                "agent_http" not in runner.capabilities.get("adapters", [])
                or not target["capabilities"].get("reconciliation")
                or not service.supports_target(runner.capabilities, target)
            ):
                continue
            attempt = session.get(Attempt, work.attempt_id)
            if attempt.status != "unknown" or attempt.execution_intent_at is None:
                continue
            if state.get("token") and session.get(ResolutionRecord, UUID(state["token"])) is None:
                session.add(
                    ResolutionRecord(
                        attempt_id=attempt.id,
                        credential_id=credential.id,
                        previous_status=attempt.status,
                        content={
                            "source": "automatic_agent_http_query",
                            "phase": "expired",
                            "query_id": state["token"],
                            "runner_id": state["runner_id"],
                            "diagnostic": "query_lease_expired_without_observation",
                        },
                    )
                )
            token = uuid4()
            count = state.get("count", 0) + 1
            # A lost query acknowledgement also backs off. Restart cannot reset it.
            delay = min(3600, 15 * 2 ** min(count - 1, 8))
            expires = current + timedelta(seconds=180)
            work.reconciliation = {
                **state,
                "count": count,
                "token": str(token),
                "runner_id": str(runner.id),
                "expires_at": expires.isoformat(),
                "due_at": (expires + timedelta(seconds=delay)).isoformat(),
            }
            session.add(
                ResolutionRecord(
                    id=claim_record_id(token),
                    attempt_id=attempt.id,
                    credential_id=credential.id,
                    previous_status=attempt.status,
                    content={
                        "source": "automatic_agent_http_query",
                        "phase": "claimed",
                        "query_id": str(token),
                        "runner_id": str(runner.id),
                        "queried_by": "idempotency_key",
                        "remote_operation_id": attempt.remote_operation_id,
                        "expires_at": expires.isoformat(),
                        "query_number": count,
                    },
                )
            )
            runner.last_seen_at = current
            return {
                "schema_version": "1.0",
                "work_item_id": work.id,
                "lease_token": token,
                "lease_expires_at": expires,
                "attempt_id": attempt.id,
                "case_run_id": work.case_run_id,
                "idempotency_key": attempt.idempotency_key,
                "remote_operation_id": attempt.remote_operation_id,
                "target": explicit_versions(TargetPublish, target, source="reconciliation_target"),
            }
    return None


def submit(session, credential, work_id, request):
    scheduling_lock(session)
    runner = service.authorized_runner(session, credential, request.runner_id)
    work = scoped(session, WorkItem, work_id, credential.project_id, lock=True)
    service.authorize_work(credential, work)
    claimed = session.get(ResolutionRecord, claim_record_id(request.lease_token))
    if (
        claimed is None
        or claimed.attempt_id != work.attempt_id
        or claimed.credential_id != credential.id
        or claimed.content["runner_id"] != str(runner.id)
    ):
        raise DomainError(409, "stale_query", "query does not belong to this Runner and work")
    fingerprint = digest(request.model_dump(mode="json"))
    previous = session.get(ResolutionRecord, request.lease_token)
    if previous:
        if previous.content["submission_digest"] != fingerprint:
            raise DomainError(409, "query_conflict", "query already has another observation")
        return {"schema_version": "1.0", "duplicate": True, "status": work.status}
    attempt = session.get(Attempt, work.attempt_id)
    state = work.reconciliation
    active = (
        work.status == "unknown"
        and attempt.status == "unknown"
        and state.get("token") == str(request.lease_token)
        and datetime.fromisoformat(state["expires_at"]) > now()
    )
    snapshot = request.snapshot
    valid = snapshot is not None and request.diagnostic == "snapshot_received"
    diagnostic = request.diagnostic
    if snapshot:
        if (
            snapshot.attempt_id != attempt.id
            or snapshot.task_id != work.case_run_id
            or (attempt.remote_operation_id and str(snapshot.run_id) != attempt.remote_operation_id)
        ):
            valid, diagnostic = False, "identity_mismatch"
        elif state.get("revision") is not None and (
            snapshot.revision < state["revision"]
            or (
                snapshot.revision == state["revision"]
                and digest(snapshot.model_dump(mode="json")) != state["snapshot_digest"]
            )
        ):
            valid, diagnostic = False, "revision_conflict"
    terminal = bool(valid and snapshot.status in TERMINAL_STATES)
    session.add(
        ResolutionRecord(
            id=request.lease_token,
            attempt_id=attempt.id,
            credential_id=credential.id,
            previous_status=attempt.status,
            content={
                "source": "automatic_agent_http_query",
                "phase": "observed",
                "query_id": str(request.lease_token),
                "runner_id": str(runner.id),
                "received_at": now().isoformat(),
                "diagnostic": diagnostic,
                "applied": active and terminal,
                "late": not active,
                "submission_digest": fingerprint,
                "snapshot": redact(snapshot.model_dump(mode="json")) if snapshot else None,
            },
        )
    )
    if active:
        delay = min(3600, 15 * 2 ** min(state["count"] - 1, 8))
        state = {
            **state,
            "due_at": (now() + timedelta(seconds=delay)).isoformat(),
            "last_diagnostic": diagnostic,
            "last_received_at": now().isoformat(),
        }
        if valid:
            attempt.remote_operation_id = str(snapshot.run_id)
            state.update(
                revision=snapshot.revision, snapshot_digest=digest(snapshot.model_dump(mode="json"))
            )
        work.reconciliation = state
        if terminal:
            result = snapshot.result
            service.resolve(
                session,
                credential,
                attempt.id,
                Resolution(
                    schema_version="1.0",
                    status=result.status,
                    reason="confirmed terminal outcome from original Agent operation",
                    stopped_confirmed=result.stopped_confirmed,
                    output=result.output,
                ),
                source="automatic_agent_http_query",
            )
    session.flush()
    return {"schema_version": "1.0", "duplicate": False, "status": work.status}
