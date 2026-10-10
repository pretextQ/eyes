import queue
import sys
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SpanProcessor
from opentelemetry.sdk.trace.id_generator import RandomIdGenerator
from opentelemetry.trace import Link, SpanContext, TraceFlags

from eyes.contracts.evidence import ExecutionEvent
from eyes.runner.files import json_bytes, redact, write_json


class AssignedIds(RandomIdGenerator):
    def __init__(self, trace_id, span_id):
        self.trace_id = int(trace_id, 16)
        self.span_id = int(span_id, 16)

    def generate_trace_id(self):
        return self.trace_id

    def generate_span_id(self):
        if self.span_id:
            value, self.span_id = self.span_id, None
            return value
        return super().generate_span_id()


class Recorder(SpanProcessor):
    """Bounded, best-effort collection. It never raises into instrumented code."""

    def __init__(self, attempt_id, traceparent, directory: Path, config, secrets=(), link=None):
        _, trace_id, root_id, _ = traceparent.split("-")
        self.attempt_id = UUID(str(attempt_id))
        self.trace_id, self.root_id = trace_id, root_id
        self.directory, self.config, self.secrets = directory, config, secrets
        self.producer = f"eyes-{uuid4()}"
        self.sequence = 0
        self.dropped = self.failures = self.truncated = 0
        try:
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        except OSError:
            self.failures += 1
        self.disk_bytes = 0
        self.lock = threading.Lock()
        self.queue = queue.Queue(maxsize=config.event_queue_size)
        self.stopping = threading.Event()
        self.worker = threading.Thread(target=self._drain, daemon=True)
        self.worker.start()
        self.provider = TracerProvider(
            id_generator=AssignedIds(trace_id, root_id), shutdown_on_exit=False
        )
        self.provider.add_span_processor(self)
        self.tracer = self.provider.get_tracer("eyes.sdk")
        links = []
        if link and link[1]:
            links = [Link(SpanContext(int(link[0], 16), int(link[1], 16), False, TraceFlags(1)))]
        self.root = self.tracer.start_span(
            "eyes.execution" if not link else "eyes.score", context=Context(), links=links
        )
        self.root_context = trace.set_span_in_context(self.root, Context())

    def on_start(self, span, parent_context=None):
        pass

    def on_end(self, span):
        try:
            context = span.get_span_context()
            self._emit(
                "span",
                {
                    "name": span.name,
                    "start_ns": span.start_time,
                    "end_ns": span.end_time,
                    "status": span.status.status_code.name,
                    "attributes": dict(span.attributes or {}),
                    "links": [
                        {
                            "trace_id": f"{link.context.trace_id:032x}",
                            "span_id": f"{link.context.span_id:016x}",
                        }
                        for link in span.links
                    ],
                    "events": [
                        {
                            "name": e.name,
                            "time_ns": e.timestamp,
                            "attributes": dict(e.attributes or {}),
                        }
                        for e in span.events
                    ],
                },
                context.span_id,
                span.parent.span_id if span.parent else None,
                "runner" if context.span_id == int(self.root_id, 16) else "sdk",
            )
        except Exception:
            with self.lock:
                self.failures += 1

    def _emit(self, kind, data, span_id, parent_id, source):
        with self.lock:
            sequence = self.sequence
            self.sequence += 1
        event = ExecutionEvent(
            event_id=uuid4(),
            producer_id=self.producer,
            attempt_id=self.attempt_id,
            trace_id=self.trace_id,
            span_id=f"{span_id:016x}",
            parent_span_id=f"{parent_id:016x}" if parent_id else None,
            sequence=sequence,
            occurred_at=datetime.now(UTC),
            type=kind,
            source=source,
            data=redact(data, self.secrets),
        ).model_dump(mode="json")
        if len(json_bytes(event)) > self.config.max_event_bytes:
            event["data"] = {"truncated": True, "reason": "event byte limit"}
            with self.lock:
                self.truncated += 1
        try:
            self.queue.put_nowait(event)
        except queue.Full:
            with self.lock:
                self.dropped += 1

    def event(self, kind, data, *, source="sdk"):
        try:
            current = trace.get_current_span().get_span_context()
            span_id = (
                current.span_id
                if current.is_valid and current.trace_id == int(self.trace_id, 16)
                else int(self.root_id, 16)
            )
            self._emit(kind, data, span_id, None, source)
        except Exception:
            with self.lock:
                self.failures += 1

    @contextmanager
    def span(self, name, attributes=None):
        # The SDK owns its provider; no global provider replacement is required.
        current = trace.get_current_span().get_span_context()
        context = (
            None
            if current.is_valid and current.trace_id == int(self.trace_id, 16)
            else self.root_context
        )
        try:
            manager = self.tracer.start_as_current_span(
                name, context=context, attributes=attributes
            )
            span = manager.__enter__()
        except Exception:
            with self.lock:
                self.failures += 1
            yield trace.NonRecordingSpan(trace.INVALID_SPAN_CONTEXT)
            return
        try:
            yield span
        except BaseException:
            try:
                manager.__exit__(*sys.exc_info())
            except Exception:
                with self.lock:
                    self.failures += 1
            raise
        else:
            try:
                manager.__exit__(None, None, None)
            except Exception:
                with self.lock:
                    self.failures += 1

    def _drain(self):
        while not self.stopping.is_set() or not self.queue.empty():
            try:
                item = self.queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                size = len(json_bytes(item))
                if self.disk_bytes + size > self.config.event_disk_bytes:
                    with self.lock:
                        self.dropped += 1
                else:
                    write_json(self.directory / f"{item['event_id']}.json", item)
                    self.disk_bytes += size
            except Exception:
                with self.lock:
                    self.failures += 1
            finally:
                self.queue.task_done()

    def force_flush(self, timeout_millis=30000):
        end = time.monotonic() + timeout_millis / 1000
        while self.queue.unfinished_tasks and time.monotonic() < end:
            time.sleep(0.01)
        return not self.queue.unfinished_tasks

    def shutdown(self):
        self.stopping.set()
        self.worker.join(timeout=1)

    def close(self):
        self.root.end()
        self.force_flush(int(self.config.evidence_wait_seconds * 1000))
        self.shutdown()
        return self.details()

    def details(self):
        with self.lock:
            return {
                "dropped_events": self.dropped,
                "capture_failures": self.failures,
                "truncated_events": self.truncated,
                "pending_events": self.queue.unfinished_tasks,
                "coverage": "explicit SDK boundaries and Runner phases",
            }
