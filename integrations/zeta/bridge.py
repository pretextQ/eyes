"""Run the local Zeta Agent through its public entry point and Eyes SDK."""

import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime

import httpx
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from zeta.app import run_agent
from zeta.hook_runtime import HookRuntime
from zeta.loop_common import RunLimitError
from zeta.runtime_base import ModelIO, RunOptions

from eyes.contracts.target import ExecutionResult


def prepare(request, context):
    """Copy the dataset's starting files into this attempt's private workspace."""
    for name, content in request.input.get("files", {}).items():
        path = (context.workspace / name).resolve()
        if (
            not path.is_relative_to(context.workspace)
            or path == context.workspace
            or path.relative_to(context.workspace).parts[0] == ".zeta"
            or not isinstance(content, str)
        ):
            raise ValueError("invalid starting file")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


async def execute(request, context):
    parameters = request.target.config["parameters"]
    key = context.secrets["model"]
    remaining = (request.deadline - datetime.now(UTC)).total_seconds() - 15
    if remaining <= 0:
        raise ValueError("insufficient time remaining to start Zeta")

    @asynccontextmanager
    async def model():
        with httpx.Client(trust_env=False) as sync_client:
            async with httpx.AsyncClient(trust_env=False) as async_client:
                yield ChatOpenAI(
                    model=parameters["model"],
                    base_url=parameters["base_url"],
                    api_key=SecretStr(key),
                    use_responses_api=False,
                    timeout=min(60, remaining),
                    max_retries=0,
                    cache=False,
                    http_client=sync_client,
                    http_async_client=async_client,
                    extra_body={"thinking": {"type": "disabled"}},
                )

    async def observe(event):
        context.event("zeta." + event.kind, asdict(event))

    runtime = HookRuntime(
        context.workspace,
        io=ModelIO(factory=model),
        options=RunOptions(
            max_requests=8,
            max_tool_calls=16,
            timeout=min(240, remaining),
            output_tokens=4096,
        ),
        listeners=[observe],
    )
    task = asyncio.create_task(
        run_agent(request.input["prompt"], context.workspace, runtime=runtime)
    )

    async def watch_cancel():
        while not context.cancel_event.is_set():
            await asyncio.sleep(0.1)
        task.cancel()

    watcher = asyncio.create_task(watch_cancel())
    status, answer, error = "succeeded", "", None
    try:
        with context.span("zeta.run"):
            answer = await task
    except RunLimitError as exc:
        status, error = "failed", type(exc).__name__
    finally:
        watcher.cancel()
        await asyncio.gather(watcher, return_exceptions=True)
        trajectory = {
            "attempt_id": str(request.attempt_id),
            "requests": runtime.requests,
            "tool_calls": runtime.tool_calls,
            "messages": [message.model_dump(mode="json") for message in runtime.history],
            "tools": [execution.result.model_dump(mode="json") for execution in runtime.executions],
        }
        root = context.workspace / ".zeta"
        root.mkdir(exist_ok=True)
        (root / "trajectory.json").write_text(
            json.dumps(trajectory, ensure_ascii=False).replace(key, "[REDACTED_API_KEY]"),
            encoding="utf-8",
        )
        context.artifact(".zeta/trajectory.json", name="zeta-trajectory.json")
    return ExecutionResult(
        status=status,
        output={
            "answer": answer,
            "model": parameters["model"],
            "requests": runtime.requests,
            "tool_calls": runtime.tool_calls,
        },
        error=error,
        cleanup_status="pending",
        evidence_status="sealed",
        dropped_events=0,
    )
