"""Strict v1 client. Transport retries never create a new business identity."""

import argparse
import base64
import hashlib
import json
import os
import threading
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import quote, urlsplit
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from eyes.adapters.http import pointer
from eyes.contracts.agent_protocol import (
    TERMINAL_STATES,
    AgentCancelResult,
    AgentCapabilities,
    AgentError,
    AgentEventPage,
    AgentResource,
    AgentResult,
    AgentRun,
    AgentTask,
)
from eyes.contracts.target import ExecutionResult, TargetCapabilities, TargetPublish, http_origin


def validate_base_url(url):
    http_origin(url)
    parsed = urlsplit(url)
    if parsed.query or parsed.fragment:
        raise ValueError("Agent base URL cannot contain query or fragment")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("remote Agent requires HTTPS")


class ResourceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input_pointer: str = Field(pattern=r"^/")
    encoding: Literal["utf8", "base64"] = "utf8"
    media_type: str = Field(default="application/octet-stream", min_length=1, max_length=200)


class AgentHttpConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    discovery: AgentCapabilities
    bearer_secret_ref: str | None = None
    poll_seconds: float = Field(default=1, ge=0.1, le=60)
    request_timeout_seconds: float = Field(default=5, ge=0.1, le=60)
    max_response_bytes: int = Field(default=1024 * 1024, ge=1024, le=8 * 1024 * 1024)
    # Logical name -> dataset input field; no host filesystem paths on the wire.
    resources: dict[str, ResourceInput] = Field(default_factory=dict, max_length=100)

    @model_validator(mode="after")
    def valid_url(self):
        validate_base_url(self.url)
        return self


def target_capabilities(discovery):
    return TargetCapabilities(
        adapter="agent_http",
        session_isolation=discovery.session_isolation,
        environment_isolation=discovery.environment_isolation,
        cancellation=discovery.cancellation,
        idempotency=True,
        reconciliation=True,
        observation=["task", "target_trace"] if discovery.events else ["task"],
    )


class ProtocolHttpError(ValueError):
    def __init__(self, status, code):
        self.status, self.code = status, code
        super().__init__(f"Agent HTTP {status}: {code}")


class AgentHttpAdapter:
    def __init__(self, config, context, allowed_origins, capabilities):
        self.config = AgentHttpConfig.model_validate(config)
        self.context, self.allowed_origins = context, allowed_origins
        self.client = httpx.Client(follow_redirects=False, trust_env=False)
        self.headers = {}
        self.lock = threading.RLock()
        self.snapshot = None
        self.task = None
        self.cursor = None
        self.events = {}
        self.sequences = {}
        self.downloaded = set()
        self.gaps = set()
        self.cancelled = threading.Event()

    def _call(self, method, path, model, *, statuses=(200,), limit=None, **kwargs):
        extra_headers = kwargs.pop("extra_headers", {})
        with self.client.stream(
            method,
            self.config.url.rstrip("/") + "/agent/v1/" + path,
            headers={**self.headers, **extra_headers},
            timeout=self.config.request_timeout_seconds,
            **kwargs,
        ) as response:
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > (limit if limit is not None else self.config.max_response_bytes):
                    raise ValueError("Agent response exceeds byte limit")
                chunks.append(chunk)
            body = b"".join(chunks)
            if response.status_code not in statuses:
                problem = AgentError.model_validate_json(body)
                raise ProtocolHttpError(response.status_code, problem.error.code)
            return response.status_code, model.model_validate_json(body) if model else body

    def prepare(self, request):
        if http_origin(self.config.url) not in self.allowed_origins:
            raise ValueError("Agent origin is not allowed by Runner")
        if self.config.bearer_secret_ref:
            self.headers = {
                "Authorization": "Bearer " + self.context.secrets[self.config.bearer_secret_ref]
            }
        _, discovered = self._call("GET", "capabilities", AgentCapabilities)
        if discovered != self.config.discovery:
            raise ValueError("Agent capabilities/version changed; publish a new target version")
        if request.target.capabilities != target_capabilities(discovered):
            raise ValueError("target capabilities do not match frozen discovery")
        if request.target.concurrency_limit > discovered.max_concurrency:
            raise ValueError("target concurrency exceeds Agent capacity")
        if request.artifact_requirements and not discovered.artifacts:
            raise ValueError("Agent does not support required artifacts")
        if self.config.resources and not discovered.resources:
            raise ValueError("Agent does not support input resources")
        if request.environment:
            raise ValueError(
                "v1 does not transmit Eyes environment; encode business setup in input"
            )
        resources = []
        for name, source in self.config.resources.items():
            content = pointer(request.input, source.input_pointer)
            if not isinstance(content, str):
                raise ValueError("resource input field must contain text or base64")
            data = (
                content.encode("utf-8")
                if source.encoding == "utf8"
                else base64.b64decode(content, validate=True)
            )
            if len(data) > self.context.config.max_artifact_bytes:
                raise ValueError("input resource exceeds byte limit")
            expected = AgentResource(
                resource_id=uuid4(),
                name=name,
                media_type=source.media_type,
                size_bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
            )
            _, actual = self._upload(expected, data)
            if actual != expected:
                raise ValueError("uploaded resource metadata mismatch")
            resources.append(actual)
        self.task = AgentTask(
            protocol_version="1.0",
            task_id=request.case_run_id,
            attempt_id=request.attempt_id,
            idempotency_key=request.idempotency_key,
            deadline=request.deadline,
            input=request.input,
            resources=resources,
            traceparent=request.traceparent,
        )

    def _upload(self, resource, data):
        return self._call(
            "PUT",
            f"resources/{resource.resource_id}",
            AgentResource,
            content=data,
            extra_headers={
                "Content-Type": resource.media_type,
                "Content-Length": str(resource.size_bytes),
                "X-Eyes-Resource-Name": quote(resource.name, safe=""),
                "X-Eyes-SHA256": resource.sha256,
            },
        )

    def _observe(self, run):
        with self.lock:
            if run.task_id != self.task.task_id or run.attempt_id != self.task.attempt_id:
                raise ValueError("Agent returned another task/attempt")
            previous = self.snapshot
            if previous:
                if run.run_id != previous.run_id:
                    raise ValueError("Agent changed run identity")
                if run.revision < previous.revision:
                    return previous
                if run.revision == previous.revision:
                    if run != previous:
                        raise ValueError("conflicting Agent revision")
                allowed = {
                    "accepted": {"accepted", "queued", "running", "cancel_requested", "unknown"}
                    | TERMINAL_STATES,
                    "queued": {"queued", "running", "cancel_requested", "unknown"}
                    | TERMINAL_STATES,
                    "running": {"running", "cancel_requested", "unknown"} | TERMINAL_STATES,
                    "cancel_requested": {"cancel_requested", "unknown"} | TERMINAL_STATES,
                    "unknown": {"unknown"} | TERMINAL_STATES,
                }
                if run.status not in allowed.get(previous.status, {previous.status}):
                    raise ValueError("Agent state regressed")
                if previous.status in TERMINAL_STATES and run.result != previous.result:
                    raise ValueError("Agent changed terminal outcome")
            else:
                self.context.remote_operation(str(run.run_id))
            self.snapshot = run
            return run

    def _by_key(self):
        _, run = self._call(
            "GET", "runs/by-key/" + quote(self.task.idempotency_key, safe=""), AgentRun
        )
        return self._observe(run)

    def execute(self, request):
        try:
            _, run = self._call(
                "POST",
                "runs",
                AgentRun,
                statuses=(200, 202),
                json=self.task.model_dump(mode="json"),
            )
        except (httpx.HTTPError, ValueError) as error:
            if isinstance(error, ProtocolHttpError) and error.status < 500:
                raise
            try:
                self._by_key()
            except ProtocolHttpError as lookup:
                if lookup.status != 404 or datetime.now(UTC) >= self.task.deadline:
                    raise
                # Exact envelope and original deadline. Core protocol guarantees deduplication.
                _, run = self._call(
                    "POST",
                    "runs",
                    AgentRun,
                    statuses=(200, 202),
                    json=self.task.model_dump(mode="json"),
                )
            else:
                run = self.snapshot
        self._observe(run)
        while True:
            result = self.reconcile(request)
            if result is not None:
                return result
            if self.cancelled.wait(self.config.poll_seconds):
                raise ValueError("Agent polling stopped; remote outcome unconfirmed")

    def reconcile(self, request):
        with self.lock:
            run = self.snapshot or self._by_key()
            _, current = self._call("GET", f"runs/{run.run_id}", AgentRun)
            run = self._observe(current)
            if self.config.discovery.events:
                try:
                    self._events(run.run_id)
                except ValueError, httpx.HTTPError:
                    self.gaps.add("event transfer failed")
            if not run.result:
                return None
            _, result = self._call("GET", f"runs/{run.run_id}/result", AgentResult)
            if result != run.result and run.status == "unknown":
                # A reliable resolution can race the separate result read.
                _, current = self._call("GET", f"runs/{run.run_id}", AgentRun)
                run = self._observe(current)
            if result != run.result:
                raise ValueError("result endpoint conflicts with run snapshot")
            return self._result(result, request)

    def _events(self, run_id):
        # Bounded drain; a live empty page retains its cursor for the next poll.
        for _ in range(1000):
            _, page = self._call(
                "GET",
                f"runs/{run_id}/events",
                AgentEventPage,
                params={"limit": 10, **({"cursor": self.cursor} if self.cursor else {})},
            )
            if page.run_id != run_id:
                raise ValueError("event page belongs to another run")
            if page.evidence.status in {"partial", "unavailable"}:
                self.gaps.add("Agent event evidence incomplete")
            for event in page.items:
                value = event.model_dump(mode="json")
                content_digest = hashlib.sha256(
                    json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
                key = str(event.event_id)
                if key in self.events:
                    if self.events[key] != content_digest:
                        raise ValueError("conflicting Agent event")
                    continue
                if event.sequence in self.sequences or (
                    self.sequences and event.sequence <= max(self.sequences)
                ):
                    raise ValueError("conflicting/out of order Agent sequence")
                if len(self.events) >= 10000:
                    raise ValueError("Agent event count exceeds capture limit")
                self.events[key], self.sequences[event.sequence] = content_digest, key
                # Preserve native timestamp/identity/source inside an explicit envelope.
                self.context.event("agent.event", value, source="target_trace")
            self.cursor = page.next_cursor
            if not page.items or page.next_cursor is None:
                if self.snapshot.result and (
                    page.next_cursor is not None or page.evidence.status == "collecting"
                ):
                    self.gaps.add("Agent events still collecting after outcome")
                return
        self.gaps.add("event drain limit reached")

    def _result(self, result, request):
        if result.artifacts and not self.config.discovery.artifacts:
            raise ValueError("Agent returned undeclared artifacts")
        for artifact in result.artifacts:
            if artifact.artifact_id in self.downloaded:
                continue
            try:
                if artifact.size_bytes > self.context.config.max_artifact_bytes:
                    raise ValueError("artifact exceeds byte limit")
                _, data = self._call(
                    "GET",
                    f"runs/{result.run_id}/artifacts/{artifact.artifact_id}",
                    None,
                    limit=self.context.config.max_artifact_bytes,
                )
                if (
                    len(data) != artifact.size_bytes
                    or hashlib.sha256(data).hexdigest() != artifact.sha256
                ):
                    raise ValueError("artifact size/digest mismatch")
                path = self.context.workspace / f".eyes-agent-{artifact.artifact_id}"
                path.write_bytes(data)
                if not self.context.artifact(
                    path, name=artifact.name, media_type=artifact.media_type
                ):
                    raise ValueError("artifact snapshot failed")
                path.unlink()
                self.downloaded.add(artifact.artifact_id)
            except OSError, ValueError, httpx.HTTPError:
                self.gaps.add("artifact transfer failed")
        names = {a.name for a in result.artifacts if a.artifact_id in self.downloaded}
        for name in request.artifact_requirements:
            if name not in names:
                self.context.event("artifact.missing", {"name": name})
                self.gaps.add("required artifact missing")
        evidence = result.evidence
        return ExecutionResult(
            status=result.status,
            output=result.output,
            error=result.error.message if result.error else None,
            remote_operation_id=str(result.run_id),
            stopped_confirmed=result.stopped_confirmed,
            cleanup_status=result.cleanup_status,
            cleanup_error="Agent cleanup failed" if result.cleanup_status == "failed" else None,
            evidence_status="partial"
            if self.gaps or evidence.status == "collecting"
            else evidence.status,
            # Internal v1 requires integer; preserve unknown explicitly and never seal it.
            dropped_events=evidence.dropped_events or 0,
            evidence_details={
                "agent_evidence": evidence.model_dump(mode="json"),
                "transfer_gaps": list(set(self.gaps)),
                "agent_completed_at": result.completed_at.isoformat()
                if result.completed_at
                else None,
            },
        )

    def cancel(self, request):
        self.cancelled.set()
        if not self.config.discovery.cancellation:
            return False
        # Resolve a response-lost submission before cancellation; never create work here.
        with self.lock:
            run = self.snapshot or self._by_key()
            _, response = self._call(
                "POST", f"runs/{run.run_id}/cancel", AgentCancelResult, statuses=(200, 202)
            )
            current = self._observe(response.run)
            # Supervisor reconciles the outcome, preserving a competing success.
            return {
                "stopped_confirmed": False,
                "agent_stopped_confirmed": bool(
                    current.result and current.result.stopped_confirmed
                ),
            }

    def cleanup(self, request):
        self.client.close()


def main():
    parser = argparse.ArgumentParser(
        description="Discover a real v1 Agent and emit TargetPublish JSON"
    )
    parser.add_argument("url")
    parser.add_argument("--name", required=True)
    parser.add_argument("--token-env")
    args = parser.parse_args()
    config = {"url": args.url}
    # Discovery does not import Runner/POSIX modules or transmit platform credentials.
    validate_base_url(args.url)
    headers = {"Authorization": "Bearer " + os.environ[args.token_env]} if args.token_env else {}
    with httpx.Client(follow_redirects=False, trust_env=False, timeout=5) as client:
        with client.stream(
            "GET", args.url.rstrip("/") + "/agent/v1/capabilities", headers=headers
        ) as response:
            response.raise_for_status()
            content = bytearray()
            for chunk in response.iter_bytes():
                if len(content) + len(chunk) > 1024 * 1024:
                    raise ValueError("discovery exceeds byte limit")
                content.extend(chunk)
            discovery = AgentCapabilities.model_validate_json(content)
    config["discovery"] = discovery.model_dump(mode="json")
    if args.token_env:
        config["bearer_secret_ref"] = "agent_auth"
    target = TargetPublish(
        name=args.name,
        external_version=discovery.agent_version,
        capabilities=target_capabilities(discovery),
        config=config,
        secret_refs={"agent_auth": "env:" + args.token_env} if args.token_env else {},
        concurrency_limit=discovery.max_concurrency,
    )
    AgentHttpConfig.model_validate(config)
    print(json.dumps(target.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
