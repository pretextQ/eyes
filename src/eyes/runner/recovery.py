"""Bounded, durable read-only transfer of an original operation's evidence."""

import asyncio
import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta

import httpx

from eyes.adapters.agent_http import AgentHttpAdapter
from eyes.common.files import atomic_write, json_bytes, redact, resolve_secrets, write_json
from eyes.contracts.agent_protocol import AgentEventPage, AgentRun
from eyes.contracts.work import ReconciliationAssignment
from eyes.runner import journal
from eyes.runner.client import ApiError
from eyes.runner.reconciliation import query_original


async def send(service, directory, job, content=None):
    # At most one pending page or artifact per work, bounded before persistence.
    data = json_bytes(job)
    pending_bytes = sum(
        p.stat().st_size for p in directory.parent.glob("*/pending.*") if p.parent != directory
    )
    if (
        service.outbox.size(strict=True) + pending_bytes + len(data) + len(content or b"")
        > service.config.outbox_bytes
    ):
        raise ValueError("recovery transfer exceeds durable byte limit")
    if content is not None:
        atomic_write(directory / "pending.content", content)
    write_json(directory / "pending.json", job)
    response = await service.client.request(
        job["method"], job["path"], json=job.get("body"), content=content
    )
    (directory / "pending.json").unlink()
    (directory / "pending.content").unlink(missing_ok=True)
    return response


async def run_one(service):
    root = service.config.state_dir / "evidence-recovery"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    retry = root / "retry.json"
    previous = json.loads(retry.read_bytes()) if retry.exists() else {}
    if previous.get("due_at") and datetime.fromisoformat(previous["due_at"]) > datetime.now(UTC):
        return
    try:
        await transfer_one(service)
        retry.unlink(missing_ok=True)
    except (ApiError, httpx.HTTPError, ValueError, OSError, KeyError, StopIteration) as error:
        count = previous.get("count", 0) + 1
        write_json(
            retry,
            {
                "count": count,
                "due_at": (
                    datetime.now(UTC) + timedelta(seconds=min(3600, 15 * 2 ** min(count - 1, 8)))
                ).isoformat(),
                "error_type": type(error).__name__,
                "code": error.code if isinstance(error, ApiError) else None,
            },
        )
        logging.getLogger(__name__).warning(
            "evidence_recovery_waiting type=%s code=%s",
            type(error).__name__,
            error.code if isinstance(error, ApiError) else None,
        )


async def transfer_one(service):
    root = service.config.state_dir / "evidence-recovery"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    query = None
    # Continue the persisted assignment while valid; after expiry the database
    # owns reallocation/backoff and its last acknowledged cursor survives.
    for path in root.glob("*/assignment.json"):
        if (path.parent / "ack.json").exists() or (path.parent / "corrupt.json").exists():
            continue
        try:
            candidate = ReconciliationAssignment.model_validate_json(path.read_bytes()).model_dump(
                mode="json"
            )
            if candidate["work_item_id"] != path.parent.name or candidate["phase"] != "evidence":
                raise ValueError("recovery journal identity mismatch")
        except ValueError as error:
            journal.corrupt(path.parent, path, error)
            continue
        if datetime.fromisoformat(candidate["lease_expires_at"]) > datetime.now(UTC):
            query = candidate
            break
    if query is None:
        response = await service.client.request(
            "POST",
            "v1/reconciliation/claim",
            json={
                "schema_version": "1.0",
                "runner_id": service.runner_id,
                "evidence_recovery": True,
            },
        )
        if response["query"] is None:
            return
        query = ReconciliationAssignment.model_validate(response["query"]).model_dump(mode="json")
    directory = root / query["work_item_id"]
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if (directory / "corrupt.json").exists():
        raise ValueError("recovery journal is isolated; preserve its original bytes")
    write_json(directory / "assignment.json", query)
    observation = await asyncio.to_thread(query_original, service.config, query)
    body = {
        "schema_version": "1.0",
        "runner_id": service.runner_id,
        "lease_token": query["lease_token"],
    }
    prefix = f"v1/work/{query['work_item_id']}/recovery-"
    verified = await service.client.request(
        "POST", prefix + "observation", json={**body, **observation}
    )
    if not verified["verified"]:
        write_json(directory / "diagnostic.json", {"diagnostic": "original_operation_not_verified"})
        raise ValueError("original operation not verified; retain evidence gap and back off")
    snapshot = AgentRun.model_validate(observation["snapshot"])
    if (
        str(snapshot.run_id) != query["remote_operation_id"]
        or str(snapshot.attempt_id) != query["attempt_id"]
        or str(snapshot.task_id) != query["case_run_id"]
    ):
        raise ValueError("remote operation identity mismatch")
    target = query["target"]
    secrets = resolve_secrets(
        target["secret_refs"], service.config.secret_env_allowlist, service.config.token_env
    )
    adapter = AgentHttpAdapter(
        target["config"], None, service.config.allowed_http_origins, target["capabilities"]
    )
    if adapter.config.bearer_secret_ref:
        adapter.headers = {"Authorization": "Bearer " + secrets[adapter.config.bearer_secret_ref]}
    try:
        pending = directory / "pending.json"
        if pending.exists():
            job = json.loads(pending.read_bytes())
            # The journal can outlive a lease. Rebind only after the same immutable
            # original result has been authenticated again, never replay business work.
            if not job["path"].startswith(prefix):
                raise ValueError("pending evidence belongs to another operation")
            if job["method"] == "POST" and job["path"] == prefix + "events":
                job["body"] = {**job["body"], **body}
                await send(service, directory, job)
            elif job["method"] == "PUT" and job["path"].startswith(prefix + "artifacts/"):
                identifier = job["path"].split("?")[0].rsplit("/", 1)[-1]
                item = next(
                    (a for a in snapshot.result.artifacts if str(a.artifact_id) == identifier), None
                )
                if item is None:
                    raise ValueError("durable artifact does not belong to original result")
                content = (directory / "pending.content").read_bytes()
                if (
                    len(content) != item.size_bytes
                    or hashlib.sha256(content).hexdigest() != item.sha256
                ):
                    raise ValueError("durable artifact integrity mismatch")
                job["path"] = prefix + f"artifacts/{identifier}?lease_token={query['lease_token']}"
                await send(service, directory, job, content)
            else:
                raise ValueError("invalid durable evidence endpoint")
            # Refresh the durable cursor after a replay (including lost ack).
            verified = await service.client.request(
                "POST", prefix + "observation", json={**body, **observation}
            )
        cursor = verified["cursor"]
        if adapter.config.discovery.events and not verified["events_done"]:
            for _ in range(1000):
                _, page = await asyncio.to_thread(
                    adapter._call,
                    "GET",
                    f"runs/{snapshot.run_id}/events",
                    AgentEventPage,
                    params={"limit": 10, **({"cursor": cursor} if cursor else {})},
                )
                if page.run_id != snapshot.run_id:
                    raise ValueError("event page identity mismatch")
                wire = redact(page.model_dump(mode="json"), secrets.values())
                if len(json_bytes(wire)) > service.config.event_disk_bytes:
                    raise ValueError("event page exceeds durable byte limit")
                await send(
                    service,
                    directory,
                    {
                        "method": "POST",
                        "path": prefix + "events",
                        "body": {**body, "cursor": cursor, "page": wire},
                    },
                )
                cursor = page.next_cursor
                if cursor is None:
                    break
            else:
                raise ValueError("event drain limit reached")
        if len(snapshot.result.artifacts) > service.config.max_artifacts:
            raise ValueError("artifact count exceeds capture limit")
        for item in snapshot.result.artifacts:
            if str(item.artifact_id) in verified["artifacts"]:
                continue
            if (
                not adapter.config.discovery.artifacts
                or item.size_bytes > service.config.max_artifact_bytes
            ):
                raise ValueError("artifact unsupported or exceeds byte limit")
            _, content = await asyncio.to_thread(
                adapter._call,
                "GET",
                f"runs/{snapshot.run_id}/artifacts/{item.artifact_id}",
                None,
                limit=service.config.max_artifact_bytes,
            )
            if (
                len(content) != item.size_bytes
                or hashlib.sha256(content).hexdigest() != item.sha256
            ):
                raise ValueError("remote artifact integrity mismatch")
            await send(
                service,
                directory,
                {
                    "method": "PUT",
                    "path": prefix
                    + f"artifacts/{item.artifact_id}?lease_token={query['lease_token']}",
                },
                content,
            )
        # Close is computed from durable server receipts, never local success guesses.
        closed = await service.client.request("POST", prefix + "close", json=body)
        write_json(directory / "ack.json", closed)
    finally:
        adapter.client.close()
