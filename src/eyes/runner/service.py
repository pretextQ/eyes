import asyncio
import json
import logging
import shutil
from datetime import UTC, datetime

import httpx

from eyes.adapters.python import PythonAdapter
from eyes.contracts.evidence import ArtifactMetadata, ExecutionEvent
from eyes.contracts.scorer import ScoreAssignment, ScoreInput, ScoreOutput
from eyes.contracts.target import ExecutionInput, ExecutionResult
from eyes.contracts.work import ClaimedWork
from eyes.runner.client import ApiError, ControlClient
from eyes.runner.files import error_text, file_digest, redact, resolve_secrets, write_json
from eyes.runner.outbox import Outbox
from eyes.runner.process import ProcessWorker, WorkerError

logger = logging.getLogger(__name__)


def remaining(deadline):
    return max(0.01, (deadline - datetime.now(UTC)).total_seconds())


class StopWork(Exception):
    pass


class Lease:
    def __init__(self, service, work):
        self.service, self.work = service, work
        self.stop = asyncio.Event()
        self.done = asyncio.Event()
        self.reason = "cancelled"
        self.valid_until = datetime.fromisoformat(work["lease_expires_at"])
        self.task = None

    @property
    def body(self):
        return {
            "schema_version": "1.0",
            "runner_id": self.service.runner_id,
            "lease_token": self.work["lease_token"],
        }

    async def heartbeat(self):
        interval = max(0.1, min(self.work["lease_seconds"] / 3, 10))
        while not self.done.is_set():
            try:
                response = await self.service.client.request(
                    "POST", f"v1/work/{self.work['work_item_id']}/heartbeat", json=self.body
                )
                self.valid_until = datetime.fromisoformat(response["lease_expires_at"])
                if response["cancel_requested"]:
                    self.reason = "cancelled"
                    self.stop.set()
            except ApiError as error:
                if not error.retryable:
                    self.reason = "lease_lost"
                    self.stop.set()
                    return
            except httpx.HTTPError:
                pass
            except Exception as error:
                logger.error("heartbeat_protocol_failure type=%s", type(error).__name__)
                self.reason = "lease_lost"
                self.stop.set()
                return
            if remaining(self.valid_until) <= self.service.config.api_timeout_seconds + 1:
                self.reason = "lease_lost"
                self.stop.set()
                return
            try:
                await asyncio.wait_for(
                    self.done.wait(), min(interval, remaining(self.valid_until) / 2)
                )
            except TimeoutError:
                pass

    async def phase(self, worker, phase, deadline, timeout=None):
        if self.stop.is_set() or self.service.stopping.is_set():
            raise StopWork(self.reason)
        task = asyncio.create_task(
            worker.call(
                phase, min(remaining(deadline), timeout) if timeout else remaining(deadline)
            )
        )
        cancelled = asyncio.create_task(self.stop.wait())
        shutdown = asyncio.create_task(self.service.stopping.wait())
        try:
            done, _ = await asyncio.wait(
                [task, cancelled, shutdown], return_when=asyncio.FIRST_COMPLETED
            )
            if task in done:
                return await task
            raise StopWork(self.reason)
        finally:
            for pending in [task, cancelled, shutdown]:
                if not pending.done():
                    pending.cancel()
            await asyncio.gather(task, cancelled, shutdown, return_exceptions=True)

    async def close(self):
        self.done.set()
        if self.task:
            await self.task


class RunnerService:
    def __init__(self, config, token):
        self.config = config
        self.client = ControlClient(config.server_url, token, config.api_timeout_seconds)
        self.outbox = Outbox(
            config.state_dir / "outbox", config.outbox_bytes, config.server_url + "\n" + token
        )
        self.work_dir = config.state_dir / "work"
        self.work_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.runner_id = None
        self.stopping = asyncio.Event()
        self.active = {"execute": set(), "score": set()}

    async def progress(self, lease, state, operation=None):
        update = {"schema_version": "1.0", "state": state}
        if operation:
            update["remote_operation_id"] = operation
        await self.client.request(
            "POST",
            f"v1/work/{lease.work['work_item_id']}/progress",
            json={**lease.body, "progress": update},
        )

    def collect(self, directory, work):
        """Move evidence into the durable outbox. Retain originals on failure."""
        evidence = directory / "capture"
        gaps = 0
        for path in sorted((evidence / "events").glob("*.json")):
            try:
                event = ExecutionEvent.model_validate_json(path.read_bytes()).model_dump(
                    mode="json"
                )
                if work["kind"] == "execute":
                    self.outbox.enqueue(
                        f"event-{event['event_id']}",
                        {
                            "kind": "events",
                            "work_id": work["work_item_id"],
                            "path": "v1/events",
                            "body": {"schema_version": "1.0", "events": [event]},
                        },
                    )
                    path.unlink()
                # Score spans are kept locally; the execution event API only
                # authorizes the execution Runner, never a scoring credential.
            except ValueError, OSError:
                gaps += 1
        for path in sorted((evidence / "artifacts").glob("*/metadata.json")):
            try:
                metadata = ArtifactMetadata.model_validate_json(path.read_bytes()).model_dump(
                    mode="json"
                )
                content = path.with_name("content").read_bytes()
                if (
                    len(content) != metadata["size"]
                    or file_digest(path.with_name("content")) != metadata["sha256"]
                ):
                    raise ValueError("local artifact integrity mismatch")
                self.outbox.enqueue(
                    f"artifact-{path.parent.name}",
                    {
                        "kind": "artifact",
                        "work_id": work["work_item_id"],
                        "attempt_id": work["payload"]["attempt_id"],
                        "metadata": metadata,
                    },
                    content,
                )
                shutil.rmtree(path.parent)
            except ValueError, OSError:
                gaps += 1
        return gaps

    def queue_completion(self, directory, work, body):
        endpoint = "execution-result" if work["kind"] == "execute" else "score-result"
        self.outbox.enqueue(
            f"result-{work['work_item_id']}",
            {
                "kind": "completion",
                "work_id": work["work_item_id"],
                "path": f"v1/work/{work['work_item_id']}/{endpoint}",
                "body": body,
                "journal_dir": str(directory),
            },
        )

    def recover(self, restarting=True):
        for directory in self.work_dir.iterdir():
            if not directory.is_dir() or not (directory / "assignment.json").exists():
                continue
            work = json.loads((directory / "assignment.json").read_bytes())
            self.collect(directory, work)
            if (directory / "result.json").exists() and not (directory / "ack.json").exists():
                try:
                    self.queue_completion(
                        directory, work, json.loads((directory / "result.json").read_bytes())
                    )
                except ValueError:
                    logger.warning("journal_waiting_for_outbox_space work=%s", work["work_item_id"])
            elif restarting and not (directory / "result.json").exists():
                # Never re-execute uncertain work or kill a stored PID after restart.
                write_json(
                    directory / "quarantine.json",
                    {"reason": "Runner restarted; reconcile the missing result through the API"},
                )

    async def complete(self, directory, work, lease, result):
        body = {**lease.body, "result": result.model_dump(mode="json")}
        write_json(directory / "result.json", body)
        self.queue_completion(directory, work, body)
        await self.outbox.flush(self.client, completions_only=True)

    async def execute(self, work, lease, directory):
        request = ExecutionInput.model_validate(work["payload"])
        binding = None
        if request.target.capabilities.adapter == "python":
            binding = self.config.python_agents.get(request.target.config.get("agent"))
            if binding is None:
                raise ValueError("Python Agent alias is not configured on this Runner")
        elif request.target.capabilities.adapter != "http":
            raise ValueError("unsupported target adapter")
        secrets = resolve_secrets(
            request.target.secret_refs, self.config.secret_env_allowlist, self.config.token_env
        )
        worker = ProcessWorker(self.config, lambda value: self._operation(lease, directory, value))
        started = intended = stopped = journal_gap = False
        result = None
        capture = {"capture_failures": 1, "reason": "worker capture did not finish"}
        try:
            await self.progress(lease, "preparing")
            await worker.start(self.init(work, directory, binding, secrets), binding)
            started = True
            await lease.phase(worker, "prepare", request.deadline)
            # Wait for committed execution intent before invoking target code.
            write_json(directory / "intent.json", {"intent": True})
            await self.progress(lease, "running")
            intended = True
            value = await lease.phase(worker, "execute", request.deadline)
            result = ExecutionResult.model_validate(value)
            try:
                write_json(
                    directory / "execution.json",
                    redact(result.model_dump(mode="json"), secrets.values()),
                )
            except OSError:
                journal_gap = True
                logger.error("execution_fact_not_persisted work=%s", work["work_item_id"])
        except (StopWork, TimeoutError) as error:
            reason = (
                "timed_out"
                if isinstance(error, TimeoutError) or remaining(request.deadline) <= 0.02
                else "cancelled"
            )
            confirmed = False
            if started and intended:
                try:
                    cancellation = await worker.call("cancel", self.config.stop_grace_seconds)
                    confirmed = cancellation is True or (
                        isinstance(cancellation, dict)
                        and cancellation.get("stopped_confirmed") is True
                    )
                    if not confirmed and request.target.capabilities.reconciliation:
                        reconciled = await worker.call("reconcile", self.config.stop_grace_seconds)
                        if reconciled:
                            candidate = ExecutionResult.model_validate(reconciled)
                            if candidate.status != "unknown":
                                result = candidate
                except WorkerError, TimeoutError, OSError, ValueError:
                    pass
            stopped = await worker.stop()
            confirmed = confirmed or (
                stopped and (not intended or (binding and binding.execution_scope == "process"))
            )
            if result is None:
                result = ExecutionResult(
                    status=reason if confirmed else "unknown",
                    stopped_confirmed=bool(confirmed),
                    error=None
                    if confirmed
                    else "target stop is unconfirmed after cancellation, deadline or lease loss",
                    cleanup_status="unknown",
                    evidence_status="partial",
                    dropped_events=0,
                )
        except (WorkerError, ApiError, httpx.HTTPError, OSError, ValueError) as error:
            # Errors after intent may leave remote effects. A declared process-only
            # binding can report its local exception as failed after group stop.
            known = not intended or bool(binding and binding.execution_scope == "process")
            result = ExecutionResult(
                status="failed" if known else "unknown",
                error=error_text(error, secrets.values()),
                cleanup_status="unknown",
                evidence_status="partial",
                dropped_events=0,
            )
        finally:
            if started and not stopped and worker.process.returncode is None:
                try:
                    await worker.call("cleanup", self.config.cleanup_timeout_seconds)
                    if result and result.cleanup_status in {"pending", "succeeded"}:
                        result.cleanup_status = "succeeded"
                        result.cleanup_error = None
                except (WorkerError, TimeoutError, OSError) as error:
                    if result:
                        result.cleanup_status = "failed"
                        result.cleanup_error = error_text(error, secrets.values())
                try:
                    capture = await worker.call("close", self.config.cleanup_timeout_seconds)
                except WorkerError, TimeoutError, OSError:
                    pass
            group_stopped = await worker.stop()
            if not group_stopped:
                if result:
                    result.status = "unknown"
                    result.stopped_confirmed = False
                    result.error = "local process group stop is unconfirmed"
                write_json(
                    directory / "quarantine.json",
                    {"reason": "local process group stop is unconfirmed"},
                )
            if result and (result.cleanup_status != "succeeded" or result.status == "unknown"):
                write_json(
                    directory / "quarantine.json",
                    {"reason": "workspace retained after unconfirmed or failed cleanup"},
                )
        operation_path = directory / "capture" / "operation.json"
        if operation_path.exists():
            result.remote_operation_id = json.loads(operation_path.read_bytes())["operation_id"]
        result.output = redact(result.output, secrets.values())
        result.error = redact(result.error, secrets.values())
        result.cleanup_error = redact(result.cleanup_error, secrets.values())
        gaps = self.collect(directory, work)
        # Evidence is uploaded before result sealing, with a bounded wait.
        try:
            await asyncio.wait_for(
                self.outbox.flush(self.client, evidence_only=True),
                self.config.evidence_wait_seconds,
            )
        except TimeoutError:
            pass
        pending, rejected = self.outbox.evidence(work["work_item_id"])
        result.dropped_events += int(capture.get("dropped_events", 0))
        result.evidence_details.update(
            {
                **capture,
                "local_transfer_failures": gaps,
                "execution_fact_persistence_failed": journal_gap,
                "pending_uploads": pending,
                "rejected_uploads": rejected,
            }
        )
        if any(
            [
                gaps,
                journal_gap,
                pending,
                rejected,
                result.dropped_events,
                capture.get("capture_failures"),
                capture.get("truncated_events"),
                capture.get("pending_events"),
                capture.get("artifact_capture_failures"),
            ]
        ):
            result.evidence_status = "partial"
        await self.complete(directory, work, lease, result)

    async def _operation(self, lease, directory, operation):
        write_json(directory / "capture" / "operation.json", {"operation_id": operation})
        try:
            await self.progress(lease, "running", operation)
        except ApiError, httpx.HTTPError:
            # The durable operation identifier survives a failed progress update.
            logger.warning(
                "remote_operation_progress_unacknowledged work=%s", lease.work["work_item_id"]
            )

    def init(self, work, directory, binding, secrets, artifact_ids=()):
        workspace = directory / "workspace"
        workspace.mkdir(exist_ok=True, mode=0o700)
        # Large task/evidence data never travels through the command pipe.
        payload_path = directory / "payload.json"
        write_json(payload_path, work["payload"])
        payload_path.chmod(0o400)
        return {
            "kind": work["kind"],
            "payload_path": str(payload_path),
            "max_payload_bytes": self.config.max_score_input_bytes
            if work["kind"] == "score"
            else self.client.max_bytes,
            "config": self.config.model_dump(mode="json"),
            "binding": binding.model_dump(mode="json") if binding else None,
            "workspace": str(workspace),
            "evidence_dir": str(directory / "capture"),
            "secrets": secrets,
            "artifact_ids": list(artifact_ids),
        }

    async def score(self, work, lease, directory):
        assignment = ScoreAssignment.model_validate(work["payload"])
        deadline = assignment.deadline
        secrets = {}
        worker = ProcessWorker(self.config, lambda value: asyncio.sleep(0))
        try:
            payload = await asyncio.wait_for(
                self.client.request(
                    "POST",
                    f"v1/work/{work['work_item_id']}/score-input",
                    json=lease.body,
                    max_bytes=self.config.max_score_input_bytes,
                ),
                remaining(deadline),
            )
            request = ScoreInput.model_validate(payload)
            if (
                request.score_run_id != assignment.score_run_id
                or request.attempt_id != assignment.attempt_id
                or request.evidence.manifest_id != assignment.manifest_id
                or request.deadline != deadline
            ):
                raise ValueError("score input does not match its frozen assignment")
            binding = self.config.python_scorers.get(request.scorer.plugin)
            if request.scorer.plugin != "rules" and binding is None:
                raise ValueError("Python scorer alias is not configured on this Runner")
            secrets = resolve_secrets(
                request.scorer.secret_refs, self.config.secret_env_allowlist, self.config.token_env
            )
            artifacts = request.evidence.artifacts
            if len(artifacts) > self.config.max_artifacts:
                raise ValueError("scoring evidence exceeds artifact count limit")
            ids = []
            for item in artifacts:
                if lease.stop.is_set() or remaining(deadline) <= 0.02:
                    raise StopWork("score cancelled or timed out")
                identifier = str(item["id"])
                metadata = ArtifactMetadata.model_validate(item["metadata_content"])
                content = await asyncio.wait_for(
                    self.client.artifact(identifier, self.config.max_artifact_bytes),
                    remaining(deadline),
                )
                import hashlib

                if (
                    len(content) != metadata.size
                    or hashlib.sha256(content).hexdigest() != metadata.sha256
                ):
                    raise ValueError("scoring artifact failed integrity verification")
                from eyes.runner.files import atomic_write

                path = directory / "workspace" / "evidence" / identifier
                atomic_write(path, content)
                path.chmod(0o400)
                ids.append(identifier)
            score_work = {**work, "payload": request.model_dump(mode="json")}
            await worker.start(self.init(score_work, directory, binding, secrets, ids), binding)
            value = await lease.phase(worker, "score", deadline)
            result = ScoreOutput.model_validate(value)
            if set(result.evidence_refs) - set(request.evidence.references):
                raise ValueError("scorer cites evidence outside its frozen manifest")
            result.reason = redact(result.reason, secrets.values())
            try:
                await worker.call("close", self.config.cleanup_timeout_seconds)
            except WorkerError, TimeoutError, OSError:
                pass
        except ApiError as error:
            result = ScoreOutput(status="insufficient_evidence", reason=error_text(error))
        except (WorkerError, StopWork, TimeoutError, OSError, ValueError, httpx.HTTPError) as error:
            result = ScoreOutput(status="error", reason=error_text(error, secrets.values()))
        finally:
            if not await worker.stop():
                write_json(
                    directory / "quarantine.json",
                    {"reason": "scorer process group stop is unconfirmed"},
                )
        if result.completed_at is None:
            result.completed_at = datetime.now(UTC)
        await self.complete(directory, work, lease, result)

    async def run_work(self, work):
        directory = self.work_dir / work["work_item_id"]
        directory.mkdir(exist_ok=False, mode=0o700)
        write_json(directory / "assignment.json", work)
        lease = Lease(self, work)
        lease.task = asyncio.create_task(lease.heartbeat())
        pump = asyncio.create_task(self.pump_evidence(directory, work))
        try:
            await (
                self.execute(work, lease, directory)
                if work["kind"] == "execute"
                else self.score(work, lease, directory)
            )
        except Exception as error:
            logger.error("work_failure work=%s type=%s", work["work_item_id"], type(error).__name__)
            if not (directory / "result.json").exists():
                result = (
                    ExecutionResult(
                        status="failed",
                        error="Runner preparation failed; inspect local configuration",
                        cleanup_status="unknown",
                        evidence_status="partial",
                        dropped_events=0,
                    )
                    if work["kind"] == "execute"
                    else ScoreOutput(status="error", reason="Runner scoring configuration failed")
                )
                # If an exception escaped after intent, its journal determines the
                # safe result; never classify an untracked execution as failed.
                if (directory / "intent.json").exists() and work["kind"] == "execute":
                    result.status = "unknown"
                    result.error = "Runner failed after execution intent; reconcile target state"
                try:
                    await self.complete(directory, work, lease, result)
                except Exception:
                    logger.error("completion_retained_in_journal work=%s", work["work_item_id"])
        finally:
            pump.cancel()
            await asyncio.gather(pump, return_exceptions=True)
            await lease.close()
            logger.info("work_finished work=%s kind=%s", work["work_item_id"], work["kind"])

    async def pump_evidence(self, directory, work):
        while True:
            await asyncio.sleep(min(self.config.poll_seconds, 2))
            self.collect(directory, work)
            await self.outbox.flush(self.client)

    def reap(self):
        for directory in self.work_dir.iterdir():
            if (directory / "ack.json").exists() and not (directory / "quarantine.json").exists():
                # Retain scoring traces locally until the operator's retention job.
                if (directory / "assignment.json").exists() and json.loads(
                    (directory / "assignment.json").read_bytes()
                )["kind"] == "score":
                    shutil.rmtree(directory / "workspace", ignore_errors=True)
                    continue
                shutil.rmtree(directory)

    async def run(self, once=False):
        self.recover()
        registration = await self.client.request(
            "POST",
            "v1/runners/register",
            json={
                "schema_version": "1.0",
                "name": self.config.name,
                "supported_schema_versions": ["1.0"],
                "adapters": (["http"] if self.config.allowed_http_origins else [])
                + (["python"] if self.config.python_agents else []),
                "scorers": ["rules", *self.config.python_scorers],
                "python_agents": {
                    alias: PythonAdapter(binding, None).capabilities().model_dump(mode="json")
                    for alias, binding in self.config.python_agents.items()
                },
                "http_origins": self.config.allowed_http_origins,
            },
        )
        if registration.get("negotiated_schema_version") != "1.0":
            raise ValueError("server negotiated an unsupported protocol version")
        self.runner_id = registration["runner_id"]
        logger.info("runner_registered runner=%s", self.runner_id)
        counts = {"execute": self.config.execution_slots, "score": self.config.score_slots}
        try:
            while not self.stopping.is_set():
                await self.outbox.flush(self.client)
                self.recover(restarting=False)
                self.reap()
                for kind, slots in counts.items():
                    self.active[kind] = {task for task in self.active[kind] if not task.done()}
                    while (
                        len(self.active[kind]) < slots
                        and self.outbox.size() < self.config.outbox_bytes * 0.75
                    ):
                        try:
                            response = await self.client.request(
                                "POST",
                                "v1/work/claim",
                                json={
                                    "schema_version": "1.0",
                                    "runner_id": self.runner_id,
                                    "kind": kind,
                                },
                            )
                        except ApiError as error:
                            if not error.retryable:
                                raise
                            break
                        except httpx.HTTPError:
                            break
                        if response["work"] is None:
                            break
                        if response.get("schema_version") != "1.0":
                            raise ValueError("server returned an unsupported protocol version")
                        work = ClaimedWork.model_validate(response["work"]).model_dump(mode="json")
                        if work["kind"] != kind:
                            raise ValueError(
                                "server assignment does not match the requested work kind"
                            )
                        task = asyncio.create_task(self.run_work(work))
                        self.active[kind].add(task)
                        if once:
                            break
                if once:
                    await asyncio.gather(
                        *(task for tasks in self.active.values() for task in tasks)
                    )
                    break
                try:
                    await asyncio.wait_for(self.stopping.wait(), self.config.poll_seconds)
                except TimeoutError:
                    pass
        finally:
            self.stopping.set()
            await asyncio.gather(
                *(task for tasks in self.active.values() for task in tasks), return_exceptions=True
            )
            await self.outbox.flush(self.client)
            await self.client.close()
