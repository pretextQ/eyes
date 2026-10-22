import asyncio
import hashlib
import json
import logging
import re
import shutil
import time
from pathlib import Path
from uuid import UUID, uuid4

import httpx

from eyes.common.files import atomic_write, json_bytes, write_json
from eyes.contracts.base import explicit_versions, read_stored_contract
from eyes.contracts.evidence import ArtifactMetadata, EventBatch, EvidenceClose
from eyes.contracts.work import (
    ExecutionSubmission,
    ReconciliationAssignment,
    ReconciliationSubmission,
    ScoreSubmission,
)
from eyes.runner import journal
from eyes.runner.client import ApiError

logger = logging.getLogger(__name__)


class OutboxCapacityError(ValueError):
    pass


def job_contract(job):
    if job["kind"] == "artifact":
        return ArtifactMetadata, "metadata"
    if job["kind"] == "events":
        return EventBatch, "body"
    if job["kind"] == "evidence_close":
        return EvidenceClose, "body"
    if job["kind"] == "completion":
        model = {
            "execution-result": ExecutionSubmission,
            "score-result": ScoreSubmission,
            "reconciliation-result": ReconciliationSubmission,
        }.get(job["path"].rsplit("/", 1)[-1])
        if model is not None:
            return model, "body"
    raise ValueError("unknown durable submission contract")


def stored_job(job):
    model, field = job_contract(job)
    return {**job, field: explicit_versions(model, job[field], source="runner_outbox")}


class Outbox:
    def __init__(self, directory: Path, max_bytes: int, identity: str):
        self.directory = directory
        self.pending = directory / "pending"
        self.rejected = directory / "rejected"
        for path in [self.pending, self.rejected]:
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
        identity_file = directory / "identity.json"
        fingerprint = hashlib.sha256(identity.encode()).hexdigest()
        if (
            identity_file.exists()
            and json.loads(identity_file.read_bytes())["fingerprint"] != fingerprint
        ):
            raise ValueError(
                "state_dir belongs to a different server or credential; use a separate directory"
            )
        write_json(identity_file, {"fingerprint": fingerprint})
        self.max_bytes = max_bytes
        self.corrupted = directory.with_name(directory.name + "-corrupt")
        self.recover_files()
        self.locks = {"completion": asyncio.Lock(), "evidence": asyncio.Lock()}
        self.retries = {}

    def retry_later(self, key):
        failures = self.retries.get(key, (0, 0))[0] + 1
        self.retries[key] = (min(failures, 6), time.monotonic() + min(60, 2 ** min(failures, 6)))

    def recover_files(self):
        # Called at startup while the Runner holds its state-directory lock.
        # Keep unpaired bytes outside the bounded sending queue for inspection.
        orphaned = self.directory.with_name(self.directory.name + "-orphaned")
        for directory, other in [
            (self.pending, self.rejected),
            (self.rejected, self.pending),
            (self.directory, self.directory),
        ]:
            for path in [*directory.glob("*.content"), *directory.glob(".writing-*")]:
                try:
                    self.recover_file(path, directory, other, orphaned)
                except OSError as error:
                    logger.warning("outbox_recovery_disk_error file=%s errno=%s", path, error.errno)

    def recover_file(self, path, directory, other, orphaned):
        if path.suffix == ".content":
            if path.with_suffix(".json").exists():
                return
            counterpart = other / path.name
            if counterpart.with_suffix(".json").exists() and not counterpart.exists():
                shutil.move(path, counterpart)
                return
        orphaned.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.move(path, orphaned / f"{directory.name}-{uuid4()}-{path.name}")
        logger.warning("outbox_orphan_preserved file=%s", path.name)

    def size(self, *, strict=False):
        try:
            return sum(path.stat().st_size for path in self.directory.rglob("*") if path.is_file())
        except OSError as error:
            logger.warning("outbox_size_disk_error errno=%s", error.errno)
            if strict:
                raise
            return self.max_bytes

    def read_job(self, path):
        job = json.loads(path.read_bytes())
        if not isinstance(job, dict):
            raise ValueError("outbox entry must be an object")
        key = job.get("key")
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9-]+", key):
            raise ValueError("invalid outbox key")
        if key != path.stem:
            raise ValueError("outbox key differs from filename")
        if not isinstance(job.get("work_id"), str):
            raise ValueError("missing work identity")
        work_id = str(UUID(job["work_id"]))
        if work_id != job["work_id"]:
            raise ValueError("noncanonical work identity")
        wire = stored_job(job)
        kind = job["kind"]
        if (self.directory.parent / "work" / work_id / "corrupt.json").exists():
            raise ValueError("associated work is isolated")
        if kind == "artifact":
            attempt = str(UUID(job["attempt_id"]))
            if attempt != job["attempt_id"]:
                raise ValueError("noncanonical attempt identity")
            content = path.with_suffix(".content").read_bytes()
            if (
                len(content) != wire["metadata"]["size"]
                or hashlib.sha256(content).hexdigest() != wire["metadata"]["sha256"]
            ):
                raise ValueError("outbox artifact content is damaged")
        elif kind == "events":
            if job["path"] != "v1/events":
                raise ValueError("invalid events path")
        else:
            directory = Path(job["journal_dir"])
            root = self.directory.parent.resolve()
            if directory.resolve().parent not in {root / "work", root / "reconciliation"}:
                raise ValueError("journal outside Runner state")
            if kind == "completion":
                endpoint = job["path"].rsplit("/", 1)[-1]
                expected = f"v1/work/{work_id}/{endpoint}"
            else:
                attempt = str(UUID(job["path"].split("/")[2]))
                expected = f"v1/attempts/{attempt}/evidence-close"
            if job["path"] != expected:
                raise ValueError("invalid submission path")
            if (directory / "corrupt.json").exists():
                raise ValueError("associated journal is isolated")
            source = directory / "assignment.json"
            try:
                if directory.resolve().parent == root / "work":
                    work = journal.assignment(directory)
                    if work["work_item_id"] != work_id:
                        raise ValueError("outbox and journal identities differ")
                    source = directory / "result.json"
                    result = journal.submission(directory, work)
                    if kind == "completion":
                        suffix = "execution-result" if work["kind"] == "execute" else "score-result"
                        if endpoint != suffix or wire["body"] != result:
                            raise ValueError("outbox differs from journal result")
                    elif attempt != work["payload"]["attempt_id"]:
                        raise ValueError("evidence close differs from assignment")
                else:
                    query = read_stored_contract(
                        ReconciliationAssignment,
                        json.loads(source.read_bytes()),
                        source="query_assignment",
                    ).model_dump(mode="json")
                    if (
                        query["work_item_id"] != work_id
                        or query["lease_token"] != directory.name
                        or query["lease_token"] != wire["body"]["lease_token"]
                        or endpoint != "reconciliation-result"
                    ):
                        raise ValueError("query journal identity mismatch")
                    source = directory / "result.json"
                    original = stored_job(json.loads(source.read_bytes()))
                    if any(wire.get(key) != value for key, value in original.items()):
                        raise ValueError("outbox differs from query result")
            except (ValueError, KeyError, TypeError, FileNotFoundError) as error:
                journal.corrupt(directory, source, error)
                raise
        return job, wire

    def isolate(self, path, error):
        logger.error("outbox_corrupt file=%s type=%s", path, type(error).__name__)
        # Move bytes unchanged, including paired content. Unknown ownership must
        # conservatively block sealing, never be inferred from malformed JSON.
        destination = self.corrupted / str(uuid4())
        work_id = None
        try:
            value = json.loads(path.read_bytes())
            if isinstance(value, dict) and isinstance(value.get("work_id"), str):
                work_id = str(UUID(value["work_id"]))
        except ValueError, OSError:
            pass
        try:
            destination.mkdir(parents=True, mode=0o700)
            write_json(
                destination / "diagnostic.json",
                {"file": path.name, "error_type": type(error).__name__, "work_id": work_id},
            )
            shutil.move(path, destination / path.name)
            content = path.with_suffix(".content")
            if content.exists():
                shutil.move(content, destination / content.name)
        except OSError as failure:
            logger.error("outbox_isolation_disk_error file=%s errno=%s", path, failure.errno)

    def load(self, path):
        try:
            return self.read_job(path)
        except (
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            IndexError,
            FileNotFoundError,
        ) as error:
            self.isolate(path, error)
        except OSError as error:
            logger.warning("outbox_read_disk_error file=%s errno=%s", path, error.errno)
        return None

    def enqueue(self, key, job, content=None, *, persisted=False):
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9-]+", key):
            raise ValueError("invalid outbox key")
        path = self.pending / f"{key}.json"
        if path.exists() or (self.rejected / path.name).exists():
            return
        if persisted:
            job = stored_job(job)
        else:
            model, field = job_contract(job)
            model.model_validate(job[field])
        job = {**job, "key": key}
        data = json_bytes(job)
        content_path = self.pending / f"{key}.content"
        replaced_bytes = content_path.stat().st_size if content_path.exists() else 0
        additional_bytes = len(data) + (len(content) if content is not None else 0)
        if (
            self.size(strict=True)
            - (replaced_bytes if content is not None else 0)
            + additional_bytes
            > self.max_bytes
        ):
            raise OutboxCapacityError("durable outbox byte limit reached")
        if content is not None:
            atomic_write(content_path, content)
        atomic_write(path, data)

    def evidence(self, work_id):
        pending = 0
        rejected = self.corrupt_count(work_id)
        for directory in [self.pending, self.rejected]:
            for path in directory.glob("*.json"):
                loaded = self.load(path)
                if loaded is None:
                    rejected += 1
                    continue
                job, _ = loaded
                if job.get("work_id") == work_id and job["kind"] in {"events", "artifact"}:
                    if directory == self.pending:
                        pending += 1
                    else:
                        rejected += 1
        return pending, rejected

    def corrupt_count(self, work_id):
        count = 0
        for path in self.corrupted.glob("*/diagnostic.json"):
            try:
                owner = json.loads(path.read_bytes()).get("work_id")
                count += owner is None or owner == work_id
            except ValueError, AttributeError, OSError:
                count += 1
        return count

    def status(self):
        return {
            "pending": len(list(self.pending.glob("*.json"))),
            "rejected": len(list(self.rejected.glob("*.json"))),
            "bytes": self.size(),
            "byte_limit": self.max_bytes,
            "corrupted": len(list(self.corrupted.glob("*/diagnostic.json"))),
            "orphaned": len(
                list(self.directory.with_name(self.directory.name + "-orphaned").glob("*"))
            ),
        }

    async def flush(self, client, limit=50, *, completions_only=False, evidence_only=False):
        sent = 0
        if not evidence_only:
            sent += await self._flush(client, "completion", limit)
        if not completions_only and sent < limit:
            sent += await self._flush(client, "evidence", limit - sent)
        return sent

    async def _flush(self, client, lane, limit):
        # A slow or failed evidence request must not hold the completion lock.
        async with self.locks[lane]:
            files = []
            for path in sorted(self.pending.glob("*.json")):
                loaded = self.load(path)
                if loaded is None:
                    continue
                job, wire = loaded
                if self.retries.get(job["key"], (0, 0))[1] > time.monotonic():
                    continue
                if (job["kind"] == "completion") == (lane == "completion"):
                    files.append((path, job, wire))
            sent = 0
            for path, job, wire in files[:limit]:
                # Validate stored bytes before transport; transport/response errors
                # must not be mistaken for a malformed journal.
                try:
                    if (
                        job["kind"] == "completion"
                        and wire["body"].get("result", {}).get("evidence_status") == "sealed"
                        and self.corrupt_count(job["work_id"])
                    ):
                        logger.warning("completion_blocked_by_corrupt_evidence file=%s", path)
                        continue
                    if job["kind"] == "evidence_close" and any(self.evidence(job["work_id"])):
                        continue
                    if job["kind"] == "artifact":
                        response = await client.request(
                            "POST",
                            f"v1/attempts/{job['attempt_id']}/artifacts",
                            json=wire["metadata"],
                        )
                        content = (self.pending / f"{job['key']}.content").read_bytes()
                        await client.request(
                            "PUT", f"v1/artifacts/{response['id']}/content", content=content
                        )
                    else:
                        await client.request("POST", job["path"], json=wire["body"])
                    if job["kind"] == "completion":
                        write_json(Path(job["journal_dir"]) / "ack.json", {"acknowledged": True})
                    if job["kind"] == "evidence_close":
                        write_json(
                            Path(job["journal_dir"]) / "evidence-ack.json", {"acknowledged": True}
                        )
                    path.unlink()
                    (self.pending / f"{job['key']}.content").unlink(missing_ok=True)
                    sent += 1
                    self.retries.pop(job["key"], None)
                except ApiError as error:
                    if error.retryable:
                        logger.warning("outbox_retry key=%s status=%s", job["key"], error.status)
                        self.retry_later(job["key"])
                        continue
                    job["rejection"] = {"status": error.status, "code": error.code}
                    try:
                        write_json(self.rejected / path.name, job)
                        content_path = self.pending / f"{job['key']}.content"
                        if content_path.exists():
                            shutil.move(content_path, self.rejected / content_path.name)
                        path.unlink()
                    except OSError as failure:
                        logger.warning(
                            "outbox_rejection_disk_error file=%s errno=%s", path, failure.errno
                        )
                        self.retry_later(job["key"])
                        continue
                    self.retries.pop(job["key"], None)
                    logger.error(
                        "outbox_rejected key=%s status=%s code=%s",
                        job["key"],
                        error.status,
                        error.code,
                    )
                except httpx.HTTPError, OSError:
                    logger.warning("outbox_transport_or_disk_error key=%s", job["key"])
                    self.retry_later(job["key"])
            return sent
