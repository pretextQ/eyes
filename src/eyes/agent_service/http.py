"""Durable single-process reference binding to an integrator-owned real backend.

SQLite is local protocol storage, never a replacement for Eyes PostgreSQL.
There is no default execution implementation or canned output.
"""

import asyncio
import fcntl
import hashlib
import hmac
import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from eyes.contracts.agent_protocol import (
    TERMINAL_STATES,
    AgentArtifact,
    AgentCancelResult,
    AgentCapabilities,
    AgentEvent,
    AgentEventPage,
    AgentEvidence,
    AgentResource,
    AgentResult,
    AgentRun,
    AgentTask,
)


def encoded(value):
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class ServiceError(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.transaction() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, key TEXT UNIQUE, attempt TEXT UNIQUE,
                    task TEXT NOT NULL, snapshot TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS resources (
                    id TEXT PRIMARY KEY, metadata TEXT NOT NULL, content BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS artifacts (
                    run TEXT, id TEXT, metadata TEXT NOT NULL, content BLOB NOT NULL,
                    PRIMARY KEY(run, id), FOREIGN KEY(run) REFERENCES runs(id));
                CREATE TABLE IF NOT EXISTS events (
                    run TEXT, sequence INTEGER, event TEXT NOT NULL,
                    PRIMARY KEY(run, sequence), FOREIGN KEY(run) REFERENCES runs(id));
            """)
        self.path.chmod(0o600)

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def get(self, db, run_id):
        row = db.execute("SELECT snapshot FROM runs WHERE id=?", (str(run_id),)).fetchone()
        if row is None:
            raise ServiceError(404, "not_found")
        return AgentRun.model_validate_json(row[0])

    def update(self, db, run):
        run.revision += 1
        run.observed_at = datetime.now(UTC)
        AgentRun.model_validate(run.model_dump())
        db.execute("UPDATE runs SET snapshot=? WHERE id=?", (encoded(run), str(run.run_id)))


class RunContext:
    """Backend-owned execution boundaries. File names never become storage paths."""

    def __init__(self, store, run_id, capabilities, max_bytes, max_events):
        self.store, self.run_id, self.capabilities = store, run_id, capabilities
        self.max_bytes, self.max_events = max_bytes, max_events
        self.lock = threading.Lock()
        self.dropped = 0

    def event(self, kind, data):
        if not self.capabilities.events:
            raise ServiceError(422, "unsupported_capability")
        with self.lock, self.store.transaction() as db:
            if self.store.get(db, self.run_id).result:
                raise ValueError("cannot append events to a published outcome")
            count = db.execute(
                "SELECT COUNT(*) FROM events WHERE run=?", (str(self.run_id),)
            ).fetchone()[0]
            event = AgentEvent(
                event_id=uuid4(),
                run_id=self.run_id,
                sequence=count,
                occurred_at=datetime.now(UTC),
                type=kind,
                data=data,
            )
            if count >= self.max_events or len(encoded(event).encode()) > 64 * 1024:
                self.dropped += 1
                return None
            db.execute(
                "INSERT INTO events VALUES(?,?,?)", (str(self.run_id), count, encoded(event))
            )
            return event.event_id

    def resource(self, resource):
        with self.store.transaction() as db:
            row = db.execute(
                "SELECT metadata,content FROM resources WHERE id=?", (str(resource.resource_id),)
            ).fetchone()
            if row is None or AgentResource.model_validate_json(row[0]) != resource:
                raise ServiceError(422, "invalid_input")
            return row[1]

    def artifact(self, name, data, media_type="application/octet-stream"):
        if not self.capabilities.artifacts:
            raise ServiceError(422, "unsupported_capability")
        if len(data) > self.max_bytes:
            raise ServiceError(413, "payload_too_large")
        artifact = AgentArtifact(
            artifact_id=uuid4(),
            name=name,
            media_type=media_type,
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        )
        with self.store.transaction() as db:
            count = db.execute(
                "SELECT COUNT(*) FROM artifacts WHERE run=?", (str(self.run_id),)
            ).fetchone()[0]
            if count >= 100:
                raise ServiceError(413, "payload_too_large")
            db.execute(
                "INSERT INTO artifacts VALUES(?,?,?,?)",
                (str(self.run_id), str(artifact.artifact_id), encoded(artifact), data),
            )
        return artifact


def create_app(
    *,
    database,
    bearer_token,
    capabilities,
    execute,
    validate_input,
    cancel=None,
    max_bytes=32 * 1024 * 1024,
    max_events=10000,
):
    """One authenticated principal and one process per durable store.

    execute(task, context) returns AgentResult (sync or async). validate_input(input)
    must enforce the published schema without starting business work. cancel(task,
    context) returns AgentResult with actual stop/outcome facts, never just a bool.
    The integrator handles deadlines, remote stops, cleanup and business isolation.
    """
    capabilities = AgentCapabilities.model_validate(capabilities)
    if capabilities.cancellation != bool(cancel):
        raise ValueError("cancellation declaration must match backend hook")
    if not bearer_token or len(bearer_token) < 32:
        raise ValueError("configure an independent high entropy Agent Bearer token")
    store = Store(database)
    pool = ThreadPoolExecutor(max_workers=capabilities.max_concurrency)
    contexts = {}
    contexts_lock = threading.Lock()

    def unknown(run_id, code):
        return AgentResult(
            protocol_version="1.0",
            run_id=run_id,
            status="unknown",
            output=None,
            error={
                "code": code,
                "message": "Backend outcome unconfirmed; explicit reconciliation required",
            },
            stopped_confirmed=False,
            completed_at=None,
            cleanup_status="unknown",
            evidence=AgentEvidence(status="partial", dropped_events=None),
        )

    def finish(result):
        result = AgentResult.model_validate(result)
        with store.transaction() as db:
            run = store.get(db, result.run_id)
            if run.status in TERMINAL_STATES:
                # A cancelled backend callback may return after a concurrent stop
                # confirmation. The original terminal outcome always wins.
                return
            for artifact in result.artifacts:
                row = db.execute(
                    "SELECT metadata FROM artifacts WHERE run=? AND id=?",
                    (str(result.run_id), str(artifact.artifact_id)),
                ).fetchone()
                if not row or AgentArtifact.model_validate_json(row[0]) != artifact:
                    raise ValueError("result artifact must be durably published by this run")
            run.status, run.result = result.status, result
            store.update(db, run)

    def invoke(task, context):
        try:
            with store.transaction() as db:
                run = store.get(db, context.run_id)
                if run.result:
                    return
                if run.status != "cancel_requested":
                    run.status = "running"
                    store.update(db, run)
            value = execute(task, context)
            if hasattr(value, "__await__"):
                value = asyncio.run(value)
            result = AgentResult.model_validate(value)
            if result.run_id != context.run_id:
                raise ValueError("backend returned another run")
            if context.dropped:
                result.evidence = AgentEvidence(
                    status="partial",
                    dropped_events=context.dropped,
                    details={"reason": "reference event buffer limit"},
                )
            finish(result)
        except Exception:
            # Exception strings can contain secrets. A raised exception does not prove stop.
            finish(unknown(context.run_id, "backend_exception"))
        finally:
            with contexts_lock:
                contexts.pop(context.run_id, None)

    @asynccontextmanager
    async def lifespan(app):
        with store.path.with_suffix(".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Preserve mapping after crashes; never replay accepted/running business work.
            with store.transaction() as db:
                for row in db.execute("SELECT snapshot FROM runs").fetchall():
                    run = AgentRun.model_validate_json(row[0])
                    if not run.result:
                        run.status, run.result = "unknown", unknown(run.run_id, "service_restarted")
                        store.update(db, run)
            try:
                yield
            finally:
                pool.shutdown(wait=True)

    app = FastAPI(lifespan=lifespan)
    # An integrator may append a reliable resolution after examining actual backend
    # facts. This is not an unauthenticated HTTP mutation or automatic replay.
    app.state.resolve_run = finish

    def authenticate(request: Request):
        if not hmac.compare_digest(
            request.headers.get("authorization", ""), "Bearer " + bearer_token
        ):
            raise ServiceError(401, "unauthenticated")

    @app.exception_handler(ServiceError)
    async def service_error(request, error):
        return JSONResponse(
            status_code=error.status,
            content={
                "protocol_version": "1.0",
                "error": {"code": error.code, "message": error.code.replace("_", " ")},
            },
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        return await service_error(request, ServiceError(400, "invalid_request"))

    @app.exception_handler(Exception)
    async def internal_error(request, error):
        return await service_error(request, ServiceError(503, "temporarily_unavailable"))

    async def body(request, limit):
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > limit:
                raise ServiceError(413, "payload_too_large")
            data.extend(chunk)
        return bytes(data)

    auth = [Depends(authenticate)]

    @app.get("/agent/v1/capabilities", dependencies=auth)
    def discovery():
        return capabilities

    @app.post("/agent/v1/runs", dependencies=auth)
    async def submit(request: Request):
        try:
            task = AgentTask.model_validate_json(await body(request, 1024 * 1024))
        except ValidationError:
            raise ServiceError(400, "invalid_request") from None
        # Canonicalize timezone and defaults before comparing structured content.
        task.deadline = task.deadline.astimezone(UTC)
        with store.transaction() as db:
            row = db.execute(
                "SELECT task,snapshot FROM runs WHERE key=?", (task.idempotency_key,)
            ).fetchone()
            if row:
                if encoded(task) != row[0]:
                    raise ServiceError(409, "idempotency_conflict")
                return JSONResponse(status_code=200, content=json.loads(row[1]))
            if db.execute("SELECT 1 FROM runs WHERE attempt=?", (str(task.attempt_id),)).fetchone():
                raise ServiceError(409, "attempt_conflict")
            if task.deadline <= datetime.now(UTC):
                raise ServiceError(422, "deadline_expired")
            try:
                validate_input(task.input)
            except Exception:
                raise ServiceError(422, "invalid_input") from None
            if task.resources and not capabilities.resources:
                raise ServiceError(422, "unsupported_capability")
            for resource in task.resources:
                row = db.execute(
                    "SELECT metadata FROM resources WHERE id=?", (str(resource.resource_id),)
                ).fetchone()
                if not row or AgentResource.model_validate_json(row[0]) != resource:
                    raise ServiceError(422, "invalid_input")
            active = sum(
                not (run.result and run.result.stopped_confirmed)
                for (snapshot,) in db.execute("SELECT snapshot FROM runs")
                for run in [AgentRun.model_validate_json(snapshot)]
            )
            if active >= capabilities.max_concurrency:
                raise ServiceError(429, "capacity_exceeded")
            run = AgentRun(
                protocol_version="1.0",
                run_id=uuid4(),
                task_id=task.task_id,
                attempt_id=task.attempt_id,
                status="accepted",
                revision=1,
                observed_at=datetime.now(UTC),
                result=None,
            )
            db.execute(
                "INSERT INTO runs VALUES(?,?,?,?,?)",
                (
                    str(run.run_id),
                    task.idempotency_key,
                    str(task.attempt_id),
                    encoded(task),
                    encoded(run),
                ),
            )
        context = RunContext(store, run.run_id, capabilities, max_bytes, max_events)
        with contexts_lock:
            contexts[run.run_id] = context
        # Business work begins only after the acceptance transaction commits.
        pool.submit(invoke, task, context)
        return JSONResponse(status_code=202, content=run.model_dump(mode="json"))

    @app.get("/agent/v1/runs/by-key/{key}", dependencies=auth)
    def by_key(key: str):
        with store.transaction() as db:
            row = db.execute("SELECT snapshot FROM runs WHERE key=?", (key,)).fetchone()
            if not row:
                raise ServiceError(404, "not_found")
            return AgentRun.model_validate_json(row[0])

    @app.get("/agent/v1/runs/{run_id}", dependencies=auth)
    def status(run_id: UUID):
        with store.transaction() as db:
            return store.get(db, run_id)

    @app.get("/agent/v1/runs/{run_id}/result", dependencies=auth)
    def result(run_id: UUID):
        run = status(run_id)
        return JSONResponse(
            status_code=200 if run.result else 202,
            content=(run.result or run).model_dump(mode="json"),
        )

    @app.post("/agent/v1/runs/{run_id}/cancel", dependencies=auth)
    def cancellation(run_id: UUID):
        if not capabilities.cancellation:
            raise ServiceError(422, "unsupported_capability")
        with store.transaction() as db:
            run = store.get(db, run_id)
            if run.status not in TERMINAL_STATES:
                if run.status != "unknown":
                    run.status = "cancel_requested"
                    store.update(db, run)
                task = AgentTask.model_validate_json(
                    db.execute("SELECT task FROM runs WHERE id=?", (str(run_id),)).fetchone()[0]
                )
            else:
                task = None
        if task:
            with contexts_lock:
                context = contexts.get(run_id)
            if context:
                value = cancel(task, context)
                if hasattr(value, "__await__"):
                    value = asyncio.run(value)
                if value is not None:
                    value = AgentResult.model_validate(value)
                    if value.run_id != run_id:
                        raise ServiceError(400, "invalid_request")
                    finish(value)
        run = status(run_id)
        response = AgentCancelResult(
            protocol_version="1.0",
            run=run,
            accepted=True,
            stopped_confirmed=bool(run.result and run.result.stopped_confirmed),
        )
        return JSONResponse(
            status_code=200 if run.result else 202, content=response.model_dump(mode="json")
        )

    @app.get("/agent/v1/runs/{run_id}/events", dependencies=auth)
    def events(run_id: UUID, cursor: str | None = None, limit: int = 200):
        if not capabilities.events:
            raise ServiceError(422, "unsupported_capability")
        if not 1 <= limit <= 200:
            raise ServiceError(400, "invalid_request")
        try:
            # Opaque to clients, scoped to this run. Never an authorization mechanism.
            prefix, offset = cursor.split(":") if cursor else (str(run_id), "0")
            offset = int(offset)
            if prefix != str(run_id) or offset < 0:
                raise ValueError()
        except ValueError:
            raise ServiceError(400, "invalid_request") from None
        with store.transaction() as db:
            run = store.get(db, run_id)
            rows = db.execute(
                "SELECT event FROM events WHERE run=? AND sequence>=? ORDER BY sequence LIMIT ?",
                (str(run_id), offset, limit + 1),
            ).fetchall()
        items = [AgentEvent.model_validate_json(row[0]) for row in rows[:limit]]
        evidence = (
            run.result.evidence
            if run.result
            else AgentEvidence(status="collecting", dropped_events=None)
        )
        more = len(rows) > limit or evidence.status == "collecting" or not run.result
        next_offset = items[-1].sequence + 1 if items else offset
        return AgentEventPage(
            protocol_version="1.0",
            run_id=run_id,
            items=items,
            next_cursor=f"{run_id}:{next_offset}" if more else None,
            evidence=evidence,
        )

    @app.put("/agent/v1/resources/{resource_id}", dependencies=auth)
    async def upload(resource_id: UUID, request: Request):
        if not capabilities.resources:
            raise ServiceError(422, "unsupported_capability")
        data = await body(request, max_bytes)
        try:
            resource = AgentResource(
                resource_id=resource_id,
                name=unquote(request.headers["x-eyes-resource-name"], errors="strict"),
                media_type=request.headers["content-type"],
                size_bytes=int(request.headers["content-length"]),
                sha256=request.headers["x-eyes-sha256"],
            )
        except KeyError, ValueError:
            raise ServiceError(400, "invalid_request") from None
        if len(data) != resource.size_bytes or hashlib.sha256(data).hexdigest() != resource.sha256:
            raise ServiceError(422, "invalid_input")
        with store.transaction() as db:
            row = db.execute(
                "SELECT metadata,content FROM resources WHERE id=?", (str(resource_id),)
            ).fetchone()
            if row:
                if row != (encoded(resource), data):
                    raise ServiceError(409, "idempotency_conflict")
            else:
                db.execute(
                    "INSERT INTO resources VALUES(?,?,?)",
                    (str(resource_id), encoded(resource), data),
                )
        return resource

    @app.get("/agent/v1/runs/{run_id}/artifacts/{artifact_id}", dependencies=auth)
    def download(run_id: UUID, artifact_id: UUID):
        if not capabilities.artifacts:
            raise ServiceError(422, "unsupported_capability")
        with store.transaction() as db:
            run = store.get(db, run_id)
            if not run.result or artifact_id not in {a.artifact_id for a in run.result.artifacts}:
                raise ServiceError(404, "not_found")
            row = db.execute(
                "SELECT metadata,content FROM artifacts WHERE run=? AND id=?",
                (str(run_id), str(artifact_id)),
            ).fetchone()
        metadata = AgentArtifact.model_validate_json(row[0])
        return Response(row[1], media_type=metadata.media_type)

    return app
