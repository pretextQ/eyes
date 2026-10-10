"""Serve the real existing MewCode event loop through the reusable v1 binding.

Run in the existing Linux MewCode environment; never modifies MewCode core.
Model configuration and workspace roots remain private to the Agent service.
"""

import asyncio
import json
import os
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from pydantic import BaseModel, ConfigDict, Field

from eyes.agent_service.http import create_app
from eyes.contracts.agent_protocol import AgentCapabilities, AgentResult
from eyes.runner.files import redact
from integrations.mewcode import bridge


class CodingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=1)
    files: dict[str, str] = Field(default_factory=dict)


def app():
    state = Path(os.environ["MEWCODE_HTTP_STATE"]).resolve()
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    parameters = json.loads(Path(os.environ["MEWCODE_PARAMETERS_FILE"]).read_text())
    key = os.environ["MEWCODE_MODEL_KEY"]
    version = os.environ["MEWCODE_HTTP_VERSION"]
    capabilities = AgentCapabilities(
        protocol_version="1.0",
        agent_id="mewcode",
        agent_version=version,
        input_schema=CodingInput.model_json_schema(),
        max_concurrency=1,
        session_isolation=True,
        environment_isolation=False,
        cancellation=False,
        resources=False,
        events=True,
        artifacts=True,
        terminal_retention_seconds=86400,
    )

    class Context:
        def __init__(self, task, runtime):
            self.runtime = runtime
            self.workspace = state / "workspaces" / str(task.attempt_id)
            self.workspace.mkdir(parents=True, exist_ok=False, mode=0o700)
            self.secrets = {"model": key}
            self.artifacts = []
            self.capture_failures = 0

        @contextmanager
        def span(self, name):
            self.event("boundary.start", {"name": name})
            try:
                yield
            finally:
                self.event("boundary.end", {"name": name})

        def event(self, kind, data):
            try:
                return self.runtime.event("custom.mewcode." + kind, redact(data, [key]))
            except Exception:
                self.capture_failures += 1
                return None

        def artifact(self, path, *, name=None):
            try:
                source = (self.workspace / path).resolve()
                if not source.is_relative_to(self.workspace) or not source.is_file():
                    raise ValueError("artifact must be inside the Agent workspace")
                if source.stat().st_size > self.runtime.max_bytes:
                    raise ValueError("artifact exceeds byte limit")
                artifact = self.runtime.artifact(name or source.name, source.read_bytes())
                self.artifacts.append(artifact)
                return artifact.artifact_id
            except Exception:
                self.capture_failures += 1
                return None

    async def execute(task, runtime):
        context = Context(task, runtime)
        # Only local Agent config is attached; Eyes scorer/expectations/credentials
        # are neither present on the wire nor passed to MewCode.
        request = SimpleNamespace(
            input=task.input,
            attempt_id=task.attempt_id,
            target=SimpleNamespace(config={"parameters": parameters}),
        )
        bridge.prepare(request, context)
        remaining = (task.deadline - datetime.now(UTC)).total_seconds()
        result = await asyncio.wait_for(bridge.execute(request, context), max(0.01, remaining))
        # Capture actual existing workspace files; no generated expected answers.
        for source in sorted(context.workspace.rglob("*")):
            if (
                source.is_file()
                and not source.is_symlink()
                and ".mewcode" not in source.relative_to(context.workspace).parts
            ):
                context.artifact(source, name=source.relative_to(context.workspace).as_posix())
        bridge.cleanup(request, context)
        stopped = bool(result.output and result.output.get("loop_completed"))
        return AgentResult(
            protocol_version="1.0",
            run_id=runtime.run_id,
            status=result.status if stopped else "unknown",
            output=result.output,
            error={
                "code": "agent_failed",
                "message": result.error or "Agent loop not confirmed complete",
            }
            if result.status != "succeeded" or not stopped
            else None,
            stopped_confirmed=stopped,
            completed_at=datetime.now(UTC) if stopped else None,
            cleanup_status="succeeded",
            evidence={
                "status": "partial" if context.capture_failures else "sealed",
                "dropped_events": 0,
                "details": {"capture_failures": context.capture_failures},
            },
            artifacts=context.artifacts,
        )

    return create_app(
        database=state / "protocol.sqlite3",
        bearer_token=os.environ["AGENT_HTTP_TOKEN"],
        capabilities=capabilities,
        execute=execute,
        validate_input=CodingInput.model_validate,
    )
