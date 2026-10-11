"""Restart-safe read-only Agent lookup, separate from execution and cleanup."""

import asyncio
import json
import logging
from urllib.parse import quote

import httpx

from eyes.adapters.agent_http import AgentHttpAdapter, target_capabilities
from eyes.contracts.agent_protocol import AgentCapabilities, AgentRun
from eyes.contracts.target import TargetPublish, http_origin
from eyes.contracts.work import ReconciliationAssignment
from eyes.runner.client import ApiError
from eyes.runner.files import redact, resolve_secrets, write_json

logger = logging.getLogger(__name__)


def query_original(config, query):
    target = TargetPublish.model_validate(query["target"])
    secrets = resolve_secrets(target.secret_refs, config.secret_env_allowlist, config.token_env)
    adapter = AgentHttpAdapter(
        target.config, None, config.allowed_http_origins, target.capabilities
    )
    try:
        if http_origin(adapter.config.url) not in config.allowed_http_origins:
            raise ValueError("Agent origin is not allowed")
        if adapter.config.bearer_secret_ref:
            adapter.headers = {
                "Authorization": "Bearer " + secrets[adapter.config.bearer_secret_ref]
            }
        _, discovered = adapter._call("GET", "capabilities", AgentCapabilities)
        if discovered != adapter.config.discovery or target.capabilities != target_capabilities(
            discovered
        ):
            return {"snapshot": None, "diagnostic": "capability_mismatch"}
        # Never call prepare/execute/cancel/cleanup: prepare can upload resources.
        _, snapshot = adapter._call(
            "GET", "runs/by-key/" + quote(query["idempotency_key"], safe=""), AgentRun
        )
        return {
            "snapshot": redact(snapshot.model_dump(mode="json"), secrets.values()),
            "diagnostic": "snapshot_received",
        }
    finally:
        adapter.client.close()


def recover(service):
    directory = service.config.state_dir / "reconciliation"
    if not directory.exists():
        return
    for path in directory.glob("*/result.json"):
        if (path.parent / "ack.json").exists():
            continue
        try:
            job = json.loads(path.read_bytes())
            service.outbox.enqueue(f"query-{path.parent.name}", job, persisted=True)
        except ValueError, OSError:
            logger.warning("query_journal_waiting query=%s", path.parent.name)


async def run_one(service):
    try:
        response = await service.client.request(
            "POST",
            "v1/reconciliation/claim",
            json={"schema_version": "1.0", "runner_id": service.runner_id},
        )
        query = response["query"]
        if query is None:
            return
        if response.get("schema_version") != "1.0":
            raise ValueError("unsupported reconciliation protocol")
        query = ReconciliationAssignment.model_validate(query).model_dump(mode="json")
        directory = service.config.state_dir / "reconciliation" / query["lease_token"]
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        write_json(directory / "assignment.json", query)
        try:
            observation = await asyncio.to_thread(query_original, service.config, query)
        except httpx.HTTPError, ValueError, KeyError, OSError:
            # Do not store remote error bodies or configuration/credential values.
            observation = {"snapshot": None, "diagnostic": "query_failed"}
        job = {
            "kind": "completion",
            "work_id": query["work_item_id"],
            "path": f"v1/work/{query['work_item_id']}/reconciliation-result",
            "journal_dir": str(directory),
            "body": {
                "schema_version": "1.0",
                "runner_id": service.runner_id,
                "lease_token": query["lease_token"],
                **observation,
            },
        }
        write_json(directory / "result.json", job)
        recover(service)
    except (ApiError, httpx.HTTPError, ValueError, OSError, KeyError) as error:
        logger.warning("reconciliation_unavailable type=%s", type(error).__name__)
