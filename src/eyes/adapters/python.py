import asyncio
import importlib
import inspect

from eyes.contracts.target import ExecutionResult, TargetCapabilities


def resolve(entry_point):
    module, attribute = entry_point.split(":", 1)
    value = importlib.import_module(module)
    for part in attribute.split("."):
        value = getattr(value, part)
    if not callable(value):
        raise ValueError("configured entry point is not callable")
    return value


def invoke(entry_point, request, context):
    value = resolve(entry_point)(request, context)
    return asyncio.run(value) if inspect.isawaitable(value) else value


def execution_result(value):
    if isinstance(value, ExecutionResult):
        return value
    if not isinstance(value, dict):
        raise ValueError("Agent must return a JSON object or ExecutionResult")
    return ExecutionResult(
        status="succeeded",
        output=value,
        cleanup_status="pending",
        evidence_status="sealed",
        dropped_events=0,
    )


class PythonAdapter:
    def __init__(self, binding, context):
        self.binding, self.context = binding, context

    def capabilities(self):
        return TargetCapabilities(
            adapter="python",
            session_isolation=self.binding.session_isolation,
            environment_isolation=self.binding.environment_isolation,
            cancellation=bool(self.binding.cancel) or self.binding.execution_scope == "process",
            reconciliation=bool(self.binding.reconcile),
            idempotency=self.binding.idempotency,
            observation=["task", "sdk"],
        )

    def prepare(self, request):
        resolve(self.binding.entry_point)
        if self.binding.prepare:
            invoke(self.binding.prepare, request, self.context)

    def execute(self, request):
        return execution_result(invoke(self.binding.entry_point, request, self.context))

    def cleanup(self, request):
        if self.binding.cleanup:
            invoke(self.binding.cleanup, request, self.context)

    def cancel(self, request):
        self.context.cancel_event.set()
        return invoke(self.binding.cancel, request, self.context) if self.binding.cancel else False

    def reconcile(self, request):
        return (
            invoke(self.binding.reconcile, request, self.context)
            if self.binding.reconcile
            else None
        )
