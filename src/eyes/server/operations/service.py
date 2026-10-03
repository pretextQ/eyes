import hashlib
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select

from eyes.server.domain import DomainError, digest
from eyes.server.evidence.service import LocalArtifactStore
from eyes.server.storage.database import maintenance_lock, scheduling_lock
from eyes.server.storage.models import (
    Artifact,
    Attempt,
    ComparisonReport,
    Event,
    EvidenceWait,
    Manifest,
    ScoreRun,
    WorkItem,
    now,
)


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def audit(session, root):
    store = LocalArtifactStore(root)
    problems = []
    counts = {"ready_artifacts": 0, "expired_artifacts": 0, "manifests": 0, "scores": 0}
    for artifact in session.scalars(select(Artifact)):
        if artifact.status == "expired":
            counts["expired_artifacts"] += 1
            continue
        if artifact.status != "ready":
            continue
        counts["ready_artifacts"] += 1
        path = store.path(artifact.storage_key)
        try:
            valid = (
                not path.is_symlink()
                and path.is_file()
                and path.stat().st_size == artifact.metadata_content["size"]
                and sha256(path) == artifact.metadata_content["sha256"]
            )
        except OSError:
            valid = False
        if not valid:
            problems.append({"kind": "artifact_integrity", "id": str(artifact.id)})
    for manifest in session.scalars(select(Manifest)):
        counts["manifests"] += 1
        if manifest.expired_at:
            continue
        if digest(manifest.content) != manifest.digest:
            problems.append({"kind": "manifest_digest", "id": str(manifest.id)})
        for key, model in (("event_ids", Event), ("artifact_ids", Artifact)):
            for identifier in manifest.content[key]:
                record = session.get(model, UUID(identifier))
                if record is None or record.attempt_id != manifest.attempt_id:
                    problems.append(
                        {
                            "kind": "manifest_reference",
                            "id": str(manifest.id),
                            "reference": identifier,
                        }
                    )
    for report in session.scalars(select(ComparisonReport)):
        if digest(report.content) != report.digest:
            problems.append({"kind": "report_digest", "id": str(report.id)})
    for score in session.scalars(select(ScoreRun)):
        counts["scores"] += 1
        manifest = session.get(Manifest, score.manifest_id)
        if (
            manifest is None
            or manifest.attempt_id != score.attempt_id
            or (
                set((score.result or {}).get("evidence_refs", []))
                - set(manifest.content["references"])
            )
        ):
            problems.append({"kind": "score_reference", "id": str(score.id)})
    return {
        "schema_version": "1.0",
        "status": "ok" if not problems else "error",
        **counts,
        "problems": problems,
    }


def retained_work(session, attempt_id):
    return bool(
        session.scalar(
            select(WorkItem.id)
            .where(
                WorkItem.attempt_id == attempt_id,
                (WorkItem.reserved.is_(True))
                | WorkItem.status.in_(["queued", "claimed", "unknown"]),
            )
            .limit(1)
        )
        or session.scalar(
            select(EvidenceWait.id)
            .where(EvidenceWait.attempt_id == attempt_id, EvidenceWait.status == "waiting")
            .limit(1)
        )
    )


def expiration_candidates(session, settings, attempt_id=None):
    query = select(Attempt).where(
        Attempt.evidence_expired_at.is_(None),
        Attempt.finished_at.is_not(None),
        Attempt.status.in_(["succeeded", "failed", "cancelled", "timed_out"]),
    )
    if attempt_id:
        query = query.where(Attempt.id == attempt_id)
    elif settings.evidence_retention_days:
        query = query.where(
            Attempt.finished_at < now() - timedelta(days=settings.evidence_retention_days)
        )
    else:
        return []
    attempts = session.scalars(query.order_by(Attempt.id).with_for_update()).all()
    eligible = [a for a in attempts if not retained_work(session, a.id)]
    if attempt_id and not eligible:
        raise DomainError(
            409,
            "retention_blocked",
            "attempt is missing, expired, unresolved, active or awaiting scoring",
        )
    return eligible


def maintain(session, settings, *, apply=False, attempt_id=None):
    maintenance_lock(session, exclusive=True)
    scheduling_lock(session)
    store = LocalArtifactStore(settings.artifact_root)
    attempts = expiration_candidates(session, settings, attempt_id)
    current = now()
    pending = []
    if attempt_id is None:
        for artifact in session.scalars(
            select(Artifact).where(
                Artifact.status == "pending",
                Artifact.created_at
                < current - timedelta(hours=settings.pending_artifact_ttl_hours),
            )
        ):
            attempt = session.get(Attempt, artifact.attempt_id)
            if (
                attempt.finished_at
                and attempt.status not in {"unknown", "cancel_requested"}
                and not retained_work(session, attempt.id)
            ):
                pending.append(artifact)
    if apply:
        for attempt in attempts:
            attempt.evidence_expired_at = current
            attempt.evidence_status = "expired"
            # Retain execution status and structured diagnostics; discard execution
            # result payloads. Dataset definitions and score reasons have separate lifetimes.
            attempt.result = {
                "schema_version": "1.0",
                "status": attempt.status,
                "output": None,
                "evidence_status": "expired",
                "source": "retention",
                "dropped_events": (attempt.result or {}).get("dropped_events"),
            }
            for event in session.scalars(select(Event).where(Event.attempt_id == attempt.id)):
                event.content = {
                    **{k: v for k, v in event.content.items() if k != "data"},
                    "data": {},
                    "expired": True,
                }
                event.expired_at = current
            for manifest in session.scalars(
                select(Manifest).where(Manifest.attempt_id == attempt.id)
            ):
                manifest.content = {
                    **{
                        k: v
                        for k, v in manifest.content.items()
                        if k not in {"input", "expectations", "result", "evidence_details"}
                    },
                    "status": "expired",
                }
                manifest.expired_at = current
            for artifact in session.scalars(
                select(Artifact).where(Artifact.attempt_id == attempt.id)
            ):
                artifact.status = "expired"
        for artifact in pending:
            artifact.status = "expired"
        session.flush()
    expired_keys = set(
        session.scalars(select(Artifact.storage_key).where(Artifact.status == "expired"))
    )
    registered = set(session.scalars(select(Artifact.storage_key)))
    garbage = []
    if store.root.exists():
        cutoff = current.timestamp() - settings.orphan_artifact_grace_hours * 3600
        for path in store.root.iterdir():
            if path.is_symlink() or not path.is_file():
                continue
            if path.name in expired_keys:
                garbage.append(path)
            elif path.stat().st_mtime < cutoff:
                if path.name.startswith((".pending-", ".health-")):
                    garbage.append(path)
                elif path.name not in registered:
                    try:
                        if str(UUID(path.name)) == path.name:
                            garbage.append(path)
                    except ValueError:
                        continue
    # The caller commits tombstones BEFORE unlinking. Crashes leave reclaimable
    # bytes, never live database references to files deleted by a rolled-back tx.
    return {
        "schema_version": "1.0",
        "mode": "apply" if apply else "preview",
        "attempts": [str(a.id) for a in attempts],
        "pending_artifacts": [str(a.id) for a in pending],
        "garbage_files": [p.name for p in garbage],
    }, garbage


def reclaim(paths):
    failures = []
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            failures.append(path.name)
    return failures
