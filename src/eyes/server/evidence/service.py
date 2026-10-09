import hashlib
import logging
import os
import tempfile
from pathlib import Path
from uuid import UUID, uuid4, uuid5

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from eyes.contracts.base import SENSITIVE_KEYS
from eyes.contracts.evidence import ArtifactMetadata, EventBatch
from eyes.server.domain import DomainError, digest, public_record, scoped
from eyes.server.storage.models import (
    Artifact,
    Attempt,
    CaseRun,
    CaseVersion,
    Credential,
    Event,
    Manifest,
    Runner,
    ScoreRun,
    WorkItem,
    now,
)


def redact(value):
    if isinstance(value, dict):
        return {
            key: "[redacted]" if key.lower().replace("-", "_") in SENSITIVE_KEYS else redact(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [redact(child) for child in value]
    return value


def authorize_attempt(session: Session, credential: Credential, attempt_id: UUID, *, lock=False):
    attempt = scoped(session, Attempt, attempt_id, credential.project_id, lock=lock)
    if credential.role == "runner":
        runner = session.get(Runner, attempt.runner_id)
        run = session.get(CaseRun, attempt.case_run_id)
        from eyes.server.storage.models import Experiment

        experiment = session.get(Experiment, run.experiment_id)
        if (
            runner.credential_id != credential.id
            or (credential.target_ids and str(experiment.target_id) not in credential.target_ids)
            or "execute" not in credential.work_kinds
        ):
            raise DomainError(403, "attempt_scope", "Runner is not authorized for this attempt")
    return attempt


def seal(session: Session, attempt: Attempt) -> Manifest:
    if attempt.evidence_expired_at:
        raise DomainError(410, "evidence_expired", "expired evidence cannot be republished")
    run = session.get(CaseRun, attempt.case_run_id)
    events = session.scalars(
        select(Event).where(Event.attempt_id == attempt.id).order_by(Event.created_at, Event.id)
    ).all()
    artifacts = session.scalars(
        select(Artifact)
        .where(Artifact.attempt_id == attempt.id, Artifact.status == "ready")
        .order_by(Artifact.created_at, Artifact.id)
    ).all()
    references = [f"case:{run.case_version_id}:input", f"case:{run.case_version_id}:expectations"]
    if attempt.result and attempt.result.get("output") is not None:
        references.append(f"attempt:{attempt.id}:output")
    references.extend(f"event:{event.id}" for event in events)
    references.extend(f"artifact:{artifact.id}" for artifact in artifacts)
    previous_version = (
        session.scalar(select(func.max(Manifest.version)).where(Manifest.attempt_id == attempt.id))
        or 0
    )
    content = {
        "schema_version": "1.0",
        "status": attempt.evidence_status,
        "references": references,
        "event_ids": [str(e.id) for e in events],
        "artifact_ids": [str(a.id) for a in artifacts],
        "dropped_events": (attempt.result or {}).get("dropped_events"),
        "coverage": "declared producer boundaries only",
        "input": session.get(CaseVersion, run.case_version_id).content["input"],
        "expectations": session.get(CaseVersion, run.case_version_id).content["expectations"],
        "result": attempt.result,
        "evidence_details": (attempt.result or {}).get("evidence_details", {}),
    }
    manifest = Manifest(
        attempt_id=attempt.id, version=previous_version + 1, content=content, digest=digest(content)
    )
    session.add(manifest)
    session.flush()
    return manifest


def ingest(session: Session, credential: Credential, batch: EventBatch):
    # A producer may send events for several attempts. Lock its deduplication
    # namespace before attempt rows, always in stable order.
    namespaces = sorted({f"{credential.project_id}:{e.producer_id}" for e in batch.events})
    for namespace in namespaces:
        session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": int.from_bytes(hashlib.sha256(namespace.encode()).digest()[:8], signed=True)},
        )
    attempts = {
        aid: authorize_attempt(session, credential, aid, lock=True)
        for aid in sorted({e.attempt_id for e in batch.events}, key=str)
    }
    receipts = []
    changed = set()
    for event in batch.events:
        attempt = attempts[event.attempt_id]
        if attempt.evidence_expired_at:
            raise DomainError(410, "evidence_expired", "expired evidence cannot be republished")
        if event.trace_id != attempt.trace_id and attempt.trace_id not in event.linked_trace_ids:
            raise DomainError(
                422, "missing_trace_link", "external trace must explicitly link to attempt trace"
            )
        raw_content = event.model_dump(mode="json")
        content_digest = digest(raw_content)
        content = redact(raw_content)
        previous = session.scalar(
            select(Event).where(
                Event.project_id == credential.project_id,
                Event.producer_id == event.producer_id,
                Event.event_id == event.event_id,
            )
        )
        if previous:
            if previous.digest != content_digest:
                logging.getLogger(__name__).warning(
                    "event_conflict project=%s producer=%s event=%s",
                    credential.project_id,
                    event.producer_id,
                    event.event_id,
                )
                raise DomainError(409, "event_conflict", "event identifier has different content")
            record = previous
        else:
            record = Event(
                project_id=credential.project_id,
                attempt_id=event.attempt_id,
                producer_id=event.producer_id,
                event_id=event.event_id,
                digest=content_digest,
                content=content,
            )
            session.add(record)
            session.flush()
            changed.add(event.attempt_id)
        receipts.append(
            {
                "event_id": event.event_id,
                "record_id": record.id,
                "received_at": record.created_at,
                "duplicate": previous is not None,
            }
        )
    for aid in changed:
        if attempts[aid].evidence_status != "collecting":
            seal(session, attempts[aid])
    return {"schema_version": "1.0", "receipts": receipts}


def view(session: Session, manifest: Manifest):
    if manifest.expired_at:
        raise DomainError(410, "evidence_expired", "evidence payloads have expired")
    content = manifest.content
    events = [session.get(Event, UUID(eid)).content for eid in content["event_ids"]]
    artifacts = [public_record(session.get(Artifact, UUID(aid))) for aid in content["artifact_ids"]]
    return {
        "schema_version": "1.0",
        "manifest_id": manifest.id,
        "status": content["status"],
        "references": content["references"],
        "events": events,
        "artifacts": artifacts,
        "dropped_events": content["dropped_events"],
    }


class ArtifactStore:
    def publish(self, key: str, content: bytes) -> None:
        raise NotImplementedError

    def path(self, key: str) -> Path:
        raise NotImplementedError


class LocalArtifactStore(ArtifactStore):
    def __init__(self, root: Path):
        self.root = root.resolve()

    def path(self, key: str) -> Path:
        # Keys are server-generated UUIDs; user-visible names never become paths.
        identifier = UUID(key)
        return self.root / str(identifier)

    def publish(self, key: str, content: bytes) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        fd, filename = tempfile.mkstemp(prefix=".pending-", dir=self.root)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(filename, self.path(key))
            dir_fd = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        finally:
            Path(filename).unlink(missing_ok=True)

    def check_ready(self) -> None:
        key = str(uuid4())
        content = b"eyes-artifact-readiness"
        try:
            self.publish(key, content)
            if self.path(key).read_bytes() != content:
                raise OSError("artifact readiness probe could not verify published bytes")
        finally:
            self.path(key).unlink(missing_ok=True)


def publish_artifact(
    session: Session,
    credential: Credential,
    artifact_id: UUID,
    content: bytes,
    store: ArtifactStore,
):
    artifact = scoped(session, Artifact, artifact_id, credential.project_id)
    attempt = authorize_attempt(session, credential, artifact.attempt_id, lock=True)
    session.refresh(artifact, with_for_update=True)
    if attempt.evidence_expired_at or artifact.status == "expired":
        raise DomainError(410, "evidence_expired", "expired artifact cannot be republished")
    metadata = artifact.metadata_content
    if (
        len(content) != metadata["size"]
        or hashlib.sha256(content).hexdigest() != metadata["sha256"]
    ):
        raise DomainError(422, "artifact_integrity", "artifact size or sha256 does not match")
    if artifact.status == "ready":
        return artifact
    store.publish(artifact.storage_key, content)
    artifact.status = "ready"
    session.flush()
    if attempt.evidence_status != "collecting":
        seal(session, attempt)
    return artifact


def initiate_artifact(
    session: Session,
    credential: Credential,
    attempt_id: UUID,
    metadata: ArtifactMetadata,
    max_bytes: int,
):
    attempt = authorize_attempt(session, credential, attempt_id, lock=True)
    if attempt.evidence_expired_at:
        raise DomainError(410, "evidence_expired", "expired evidence cannot be republished")
    if metadata.size > max_bytes:
        raise DomainError(413, "artifact_too_large", "artifact exceeds configured size limit")
    content = metadata.model_dump(mode="json")
    artifact_id = uuid5(attempt_id, digest(content))
    previous = session.get(Artifact, artifact_id)
    if previous is not None:
        return previous
    artifact = Artifact(
        id=artifact_id,
        project_id=credential.project_id,
        attempt_id=attempt_id,
        metadata_content=content,
        storage_key=str(artifact_id),
    )
    session.add(artifact)
    session.flush()
    artifact.storage_key = str(artifact.id)
    return artifact


def download_path(
    session: Session, credential: Credential, artifact_id: UUID, store: ArtifactStore
):
    artifact = scoped(session, Artifact, artifact_id, credential.project_id)
    if credential.role == "runner":
        runner = session.scalar(select(Runner).where(Runner.credential_id == credential.id))
        if runner is None:
            raise DomainError(403, "artifact_scope", "Runner is not registered")
        eligible = False
        for work in session.scalars(
            select(WorkItem).where(
                WorkItem.runner_id == runner.id,
                WorkItem.attempt_id == artifact.attempt_id,
            )
        ):
            if work.kind not in credential.work_kinds or (
                credential.target_ids and str(work.target_id) not in credential.target_ids
            ):
                continue
            if work.kind == "execute":
                eligible = True
            else:
                score = session.get(ScoreRun, work.score_run_id)
                manifest = session.get(Manifest, score.manifest_id)
                eligible = str(artifact.id) in manifest.content["artifact_ids"]
            if eligible:
                break
        if not eligible:
            raise DomainError(403, "artifact_scope", "Runner has no work authorizing this artifact")
    path = store.path(artifact.storage_key)
    if artifact.status != "ready" or not path.is_file():
        raise DomainError(410, "artifact_unavailable", "artifact is pending, missing or expired")
    return path


def close(session, credential, attempt_id, request):
    attempt = authorize_attempt(session, credential, attempt_id, lock=True)
    if attempt.evidence_expired_at:
        raise DomainError(410, "evidence_expired", "expired evidence cannot be republished")
    if attempt.finished_at is None or attempt.status == "unknown":
        raise DomainError(
            409, "execution_unresolved", "finish or reconcile execution before closing evidence"
        )
    if request.status == "sealed" and session.scalar(
        select(Artifact.id)
        .where(Artifact.attempt_id == attempt_id, Artifact.status == "pending")
        .limit(1)
    ):
        raise DomainError(409, "uploads_pending", "pending uploads prevent sealing evidence")
    update = {
        "evidence_status": request.status,
        "dropped_events": request.dropped_events,
        "evidence_details": redact(request.details),
    }
    if all((attempt.result or {}).get(k) == v for k, v in update.items()):
        return session.scalar(
            select(Manifest)
            .where(Manifest.attempt_id == attempt.id)
            .order_by(Manifest.version.desc())
            .limit(1)
        )
    attempt.result = {**(attempt.result or {}), **update, "evidence_closed_at": now().isoformat()}
    attempt.evidence_status = request.status
    return seal(session, attempt)
