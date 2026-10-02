import asyncio
import hashlib
import json
import logging
import shutil
from pathlib import Path

import httpx

from eyes.runner.client import ApiError
from eyes.runner.files import atomic_write, json_bytes, write_json

logger = logging.getLogger(__name__)


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
        self.locks = {"completion": asyncio.Lock(), "evidence": asyncio.Lock()}

    def size(self):
        return sum(path.stat().st_size for path in self.directory.rglob("*") if path.is_file())

    def enqueue(self, key, job, content=None):
        path = self.pending / f"{key}.json"
        if path.exists() or (self.rejected / path.name).exists():
            return
        job = {**job, "key": key}
        data = json_bytes(job)
        if self.size() + len(data) + (len(content) if content else 0) > self.max_bytes:
            raise ValueError("durable outbox byte limit reached")
        if content is not None:
            atomic_write(self.pending / f"{key}.content", content)
        atomic_write(path, data)

    def evidence(self, work_id):
        pending = rejected = 0
        for directory in [self.pending, self.rejected]:
            for path in directory.glob("*.json"):
                job = json.loads(path.read_bytes())
                if job.get("work_id") == work_id and job["kind"] != "completion":
                    if directory == self.pending:
                        pending += 1
                    else:
                        rejected += 1
        return pending, rejected

    def status(self):
        return {
            "pending": len(list(self.pending.glob("*.json"))),
            "rejected": len(list(self.rejected.glob("*.json"))),
            "bytes": self.size(),
            "byte_limit": self.max_bytes,
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
                job = json.loads(path.read_bytes())
                if (job["kind"] == "completion") == (lane == "completion"):
                    files.append((path, job))
            sent = 0
            for path, job in files[:limit]:
                try:
                    if job["kind"] == "artifact":
                        response = await client.request(
                            "POST",
                            f"v1/attempts/{job['attempt_id']}/artifacts",
                            json=job["metadata"],
                        )
                        content = (self.pending / f"{job['key']}.content").read_bytes()
                        await client.request(
                            "PUT", f"v1/artifacts/{response['id']}/content", content=content
                        )
                    else:
                        await client.request("POST", job["path"], json=job["body"])
                    if job["kind"] == "completion":
                        write_json(Path(job["journal_dir"]) / "ack.json", {"acknowledged": True})
                    path.unlink()
                    (self.pending / f"{job['key']}.content").unlink(missing_ok=True)
                    sent += 1
                except ApiError as error:
                    if error.retryable:
                        logger.warning("outbox_retry key=%s status=%s", job["key"], error.status)
                        break
                    job["rejection"] = {"status": error.status, "code": error.code}
                    write_json(self.rejected / path.name, job)
                    content_path = self.pending / f"{job['key']}.content"
                    if content_path.exists():
                        shutil.move(content_path, self.rejected / content_path.name)
                    path.unlink()
                    logger.error(
                        "outbox_rejected key=%s status=%s code=%s",
                        job["key"],
                        error.status,
                        error.code,
                    )
                except httpx.HTTPError, OSError:
                    logger.warning("outbox_transport_or_disk_error key=%s", job["key"])
                    break
            return sent
