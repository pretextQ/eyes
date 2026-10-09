"""Eyes Python integration for the existing MewCode Agent event loop."""

import json
from dataclasses import asdict

from mewcode.agent import Agent, ErrorEvent, LoopComplete, PermissionRequest, PermissionResponse
from mewcode.client import create_client
from mewcode.config import ProviderConfig
from mewcode.conversation import ConversationManager
from mewcode.permissions import (
    DangerousCommandDetector,
    PathSandbox,
    PermissionChecker,
    PermissionMode,
    RuleEngine,
)
from mewcode.tools import create_default_registry

from eyes.contracts.target import ExecutionResult
from eyes.runner.files import redact


def prepare(request, context):
    for name, content in request.input.get("files", {}).items():
        path = (context.workspace / name).resolve()
        if not path.is_relative_to(context.workspace) or path == context.workspace:
            raise ValueError("starting file must be inside the workspace")
        if name.startswith(".mewcode/") or not isinstance(content, str):
            raise ValueError("invalid starting file")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


async def execute(request, context):
    parameters = request.target.config["parameters"]
    key = context.secrets["model"]
    provider = ProviderConfig(api_key=key, **parameters["provider"])
    registry = create_default_registry().bind_work_dir(str(context.workspace))
    checker = PermissionChecker(
        detector=DangerousCommandDetector(),
        sandbox=PathSandbox(str(context.workspace)),
        rule_engine=RuleEngine(),
        mode=PermissionMode(parameters["permission_mode"]),
    )
    agent = Agent(
        client=create_client(provider),
        registry=registry,
        protocol=provider.protocol,
        work_dir=str(context.workspace),
        permission_checker=checker,
        max_iterations=parameters["max_iterations"],
        context_window=provider.get_context_window(),
    )
    agent.session_id = str(request.attempt_id)
    conversation = ConversationManager()
    conversation.add_user_message(request.input["prompt"])
    records, errors = [], []
    completed = False

    async def consume():
        nonlocal completed
        async for event in agent.run(conversation):
            if isinstance(event, PermissionRequest):
                event.future.set_result(PermissionResponse.DENY)
                record = {"type": "permission_denied", "tool_name": event.tool_name}
            else:
                record = {"type": type(event).__name__, "data": asdict(event)}
            record = redact(record, [key])
            # Text deltas are retained in the trajectory, not sent as tiny SDK events.
            records.append(record)
            if record["type"] not in {"StreamText", "ThinkingText"}:
                context.event("mewcode." + record["type"], record)
            if isinstance(event, ErrorEvent):
                errors.append(record["data"]["message"])
            if isinstance(event, LoopComplete):
                completed = True

    with context.span("mewcode.run"):
        await consume()
    messages = [asdict(message) for message in conversation.history]
    answer = next((m["content"] for m in reversed(messages) if m["role"] == "assistant"), "")
    output = redact(
        {
            "answer": answer,
            "session_id": agent.session_id,
            "model": provider.model,
            "input_tokens": agent.total_input_tokens,
            "output_tokens": agent.total_output_tokens,
            "loop_completed": completed,
            "errors": errors,
        },
        [key],
    )
    trajectory = {"output": output, "events": records, "messages": messages}
    path = context.workspace / ".mewcode" / "eyes-trajectory.json"
    path.write_text(json.dumps(redact(trajectory, [key]), ensure_ascii=False), encoding="utf-8")
    context.artifact(".mewcode/eyes-trajectory.json", name="mewcode-trajectory.json")
    return ExecutionResult(
        status="succeeded" if completed and not errors else "failed",
        output=output,
        error="; ".join(errors) or (None if completed else "Agent loop did not complete"),
        cleanup_status="pending",
        evidence_status="sealed",
        dropped_events=0,
    )


def cleanup(request, context):
    """No persistent external service is owned by this integration."""
