"""Append evidence separately from outcomes, billing settlement and cleanup."""

import hashlib
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select

from eyes.contracts.target import Resolution
from eyes.server.domain import DomainError, digest, scoped
from eyes.server.evidence.service import redact
from eyes.server.scheduling import service
from eyes.server.storage.database import scheduling_lock
from eyes.server.storage.models import Attempt, ResolutionRecord, WorkItem


def submit(session, credential, attempt_id, request):
    if credential.role != "manage" or credential.revoked:
        raise DomainError(403, "permission_denied", "manager credential required")
    scheduling_lock(session)
    attempt = scoped(session, Attempt, attempt_id, credential.project_id, lock=True)
    if (
        request.expected_attempt_id != attempt.id
        or request.expected_task_id != attempt.case_run_id
        or request.expected_run_id != attempt.remote_operation_id
        or request.idempotency_key_sha256
        != hashlib.sha256(attempt.idempotency_key.encode()).hexdigest()
    ):
        raise DomainError(
            409, "identity_mismatch", "evidence does not identify the original operation"
        )
    record_id = uuid5(
        NAMESPACE_URL, f"eyes:manual-evidence:{credential.project_id}:{request.evidence_id}"
    )
    fingerprint = digest(request.model_dump(mode="json"))
    previous = session.get(ResolutionRecord, record_id)
    if previous:
        if (
            previous.attempt_id != attempt.id
            or previous.content["submission_digest"] != fingerprint
        ):
            raise DomainError(409, "evidence_conflict", "evidence identifier has different content")
        return previous.content["receipt"]
    if attempt.status not in {"unknown", "cancel_requested"}:
        raise DomainError(409, "not_unresolved", "only unresolved execution accepts new evidence")
    for recorded in session.scalars(
        select(ResolutionRecord).where(ResolutionRecord.attempt_id == attempt.id)
    ):
        old = recorded.content.get("evidence", {})
        if recorded.content.get("source") == "manager_evidence_reconciliation" and (
            (old.get("status") and request.status and old["status"] != request.status)
            or (
                old.get("billing", "unconfirmed") != "unconfirmed"
                and request.billing != "unconfirmed"
                and old["billing"] != request.billing
            )
        ):
            raise DomainError(409, "evidence_conflict", "previous evidence asserts another fact")
    work = session.scalar(
        select(WorkItem)
        .where(WorkItem.attempt_id == attempt.id, WorkItem.kind == "execute")
        .with_for_update()
    )

    def facts():
        return {
            "status": attempt.status,
            "reserved": work.reserved,
            "cleanup_status": attempt.cleanup_status,
            "result": attempt.result,
        }

    before = facts()
    if request.apply:
        service.resolve(
            session,
            credential,
            attempt.id,
            Resolution(
                schema_version="1.0",
                status=request.status,
                reason=request.reason,
                stopped_confirmed=True,
                output=request.output,
            ),
            source="manager_evidence_reconciliation",
        )
    receipt = {
        "schema_version": "1.0",
        "evidence_id": str(request.evidence_id),
        "attempt_id": str(attempt.id),
        "applied": request.apply,
        "status": attempt.status,
        "reserved": work.reserved,
        "billing_settled": False,
        "cleanup_status": attempt.cleanup_status,
    }
    session.add(
        ResolutionRecord(
            id=record_id,
            attempt_id=attempt.id,
            credential_id=credential.id,
            previous_status=before["status"],
            content={
                "source": "manager_evidence_reconciliation",
                "submission_digest": fingerprint,
                "evidence": redact(request.model_dump(mode="json")),
                "before": redact(before),
                "after": redact(facts()),
                "receipt": receipt,
            },
        )
    )
    session.flush()
    return receipt
