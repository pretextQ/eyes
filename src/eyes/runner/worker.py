"""Private JSON-line process protocol. Only locally approved plugins run here."""

import inspect
import json
import os
import resource
import signal
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from eyes.adapters.http import HttpAdapter
from eyes.adapters.python import PythonAdapter, invoke, resolve
from eyes.contracts.scorer import ScoreInput, ScoreOutput
from eyes.contracts.target import ExecutionInput
from eyes.runner.config import Binding, RunnerConfig
from eyes.runner.files import error_text, file_digest, json_bytes, redact, write_json
from eyes.scorers import rules
from eyes.sdk.context import AgentContext, ScoreContext
from eyes.sdk.recorder import Recorder


def implementation_digest(binding=None):
    if binding and binding.implementation_digest:
        return binding.implementation_digest
    function = resolve(binding.entry_point) if binding else rules.score
    path = inspect.getsourcefile(function)
    if not path:
        raise ValueError("plugin has no source file; configure implementation_digest explicitly")
    return file_digest(Path(path))


class DiscardedOutput:
    def __init__(self):
        self.bytes = 0
        self.lock = threading.Lock()

    @property
    def encoding(self):
        return "utf-8"

    @property
    def buffer(self):
        return self

    def fileno(self):
        return 1

    def write(self, value):
        with self.lock:
            self.bytes += len(
                value if isinstance(value, bytes) else value.encode("utf-8", errors="replace")
            )
        return len(value)

    def flush(self):
        pass

    def isatty(self):
        return False


def main():
    # Duplicate the control stream, then discard OS stdout/stderr too. Native
    # extensions and subprocesses must not corrupt the control protocol.
    protocol = os.fdopen(os.dup(sys.stdout.fileno()), "w", buffering=1)
    null = os.open(os.devnull, os.O_WRONLY)
    os.dup2(null, 1)
    os.dup2(null, 2)
    os.close(null)
    discarded = DiscardedOutput()
    sys.stdout = sys.stderr = discarded
    write_lock = threading.Lock()
    first = sys.stdin.buffer.readline(8 * 1024 * 1024 + 1)
    init = json.loads(first)
    config = RunnerConfig.model_validate(init["config"])
    binding = Binding.model_validate(init["binding"]) if init.get("binding") else None
    if binding:
        sys.path[:0] = [str(path) for path in binding.import_paths]
        for key, value in [
            (resource.RLIMIT_CPU, binding.cpu_seconds),
            (resource.RLIMIT_AS, binding.memory_bytes),
            (resource.RLIMIT_FSIZE, binding.file_bytes),
        ]:
            if value is not None:
                _, hard = resource.getrlimit(key)
                resource.setrlimit(
                    key, (min(value, hard) if hard != resource.RLIM_INFINITY else value, hard)
                )
    workspace = Path(init["workspace"])
    os.chdir(workspace)
    evidence_dir = Path(init["evidence_dir"])
    secrets = init["secrets"]
    secret_values = list(secrets.values())
    with Path(init["payload_path"]).open("rb") as payload_file:
        payload_bytes = payload_file.read(init["max_payload_bytes"] + 1)
    if len(payload_bytes) > init["max_payload_bytes"]:
        raise ValueError("worker payload exceeds configured byte limit")
    request = (
        ExecutionInput.model_validate_json(payload_bytes)
        if init["kind"] == "execute"
        else ScoreInput.model_validate_json(payload_bytes)
    )

    def emit(value):
        data = json_bytes(redact(value, secret_values))
        if len(data) > config.max_message_bytes:
            data = json_bytes(
                {"id": value.get("id"), "error": "worker response exceeds message byte limit"}
            )
        with write_lock:
            protocol.write(data.decode() + "\n")

    def operation(identifier):
        write_json(evidence_dir / "operation.json", {"operation_id": identifier})
        emit({"operation_id": identifier})

    recorder = Recorder(
        request.attempt_id,
        request.traceparent,
        evidence_dir / "events",
        config,
        secret_values,
        (request.execution_trace_id, request.execution_root_span_id)
        if init["kind"] == "score"
        else None,
    )
    if init["kind"] == "execute":
        context = AgentContext(workspace, evidence_dir, recorder, secrets, config, operation)
        adapter = (
            PythonAdapter(binding, context)
            if binding
            else HttpAdapter(
                request.target.config,
                context,
                config.allowed_http_origins,
                request.target.capabilities,
            )
        )
    else:
        context = ScoreContext(workspace, recorder, secrets, init.get("artifact_ids", []))
        adapter = None
    executor = ThreadPoolExecutor(max_workers=2)
    busy = threading.Lock()

    def run(message):
        phase = message["phase"]
        acquired = False
        try:
            if phase not in {"cancel", "reconcile"}:
                acquired = busy.acquire(blocking=False)
                if not acquired:
                    raise RuntimeError("worker is busy")
            with recorder.span(f"eyes.{phase}"):
                if phase == "prepare":
                    if binding:
                        available = adapter.capabilities()
                        requested = request.target.capabilities
                        for key in [
                            "session_isolation",
                            "environment_isolation",
                            "cancellation",
                            "idempotency",
                            "reconciliation",
                        ]:
                            if getattr(requested, key) and not getattr(available, key):
                                raise ValueError(
                                    f"local binding does not support declared capability: {key}"
                                )
                        if set(requested.observation) - set(available.observation):
                            raise ValueError(
                                "local binding does not support declared observation scope"
                            )
                    adapter.prepare(request)
                    result = None
                elif phase == "execute":
                    result = adapter.execute(request).model_dump(mode="json")
                    if binding:
                        for required in request.artifact_requirements:
                            path = (context.workspace / required).resolve()
                            if path.is_relative_to(context.workspace) and not path.exists():
                                context.event("artifact.missing", {"name": required})
                            else:
                                context.artifact(required, name=required)
                elif phase == "cleanup":
                    adapter.cleanup(request)
                    result = None
                elif phase in {"cancel", "reconcile"}:
                    result = getattr(adapter, phase)(request)
                    if hasattr(result, "model_dump"):
                        result = result.model_dump(mode="json")
                elif phase == "score":
                    if implementation_digest(binding) != request.scorer.implementation_digest:
                        raise ValueError("scorer implementation digest differs from frozen version")
                    result = (
                        invoke(binding.entry_point, request, context)
                        if binding
                        else rules.score(request, context)
                    )
                    result = ScoreOutput.model_validate(result)
                    result.completed_at = datetime.now(UTC)
                    result = result.model_dump(mode="json")
                else:
                    raise ValueError("unsupported worker phase")
            response = {"id": message["id"], "result": result}
        except Exception as error:
            response = {"id": message["id"], "error": error_text(error, secret_values)}
        finally:
            if acquired:
                busy.release()
        emit(response)

    emit({"ready": True})
    closed = False
    try:
        while True:
            line = sys.stdin.buffer.readline(config.max_message_bytes + 1)
            if not line:
                break
            if len(line) > config.max_message_bytes:
                raise ValueError("worker command exceeds byte limit")
            message = json.loads(line)
            if message.get("phase") == "close":
                if not busy.acquire(blocking=False):
                    emit({"id": message["id"], "error": "worker still executing"})
                    continue
                details = recorder.close()
                details["discarded_log_bytes"] = discarded.bytes
                details["artifact_capture_failures"] = getattr(context, "artifact_errors", 0)
                write_json(evidence_dir / "capture.json", details)
                emit({"id": message["id"], "result": details})
                busy.release()
                closed = True
                break
            executor.submit(run, message)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
        if not closed:
            # EOF means the supervisor disappeared. Stop the local group; this
            # makes no claim about remote operations or detached sessions.
            if hasattr(context, "cancel_event"):
                context.cancel_event.set()
            os.killpg(os.getpgrp(), signal.SIGTERM)


if __name__ == "__main__":
    main()
