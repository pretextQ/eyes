import asyncio
import os
import signal
import sys
from uuid import uuid4

from eyes.runner.files import json_bytes


class WorkerError(Exception):
    pass


class ProcessWorker:
    def __init__(self, config, operation):
        self.config, self.operation = config, operation
        self.process = None
        self.pending = {}
        self.ready = None
        self.reader = None
        self.write_lock = asyncio.Lock()
        self.operations = set()
        self.stop_confirmed = None

    async def start(self, init, binding):
        self.ready = asyncio.get_running_loop().create_future()
        # Plugins receive only explicitly resolved secrets via stdin; the
        # control-plane token is absent from their environment and payload.
        environment = {
            key: os.environ[key]
            for key in ["PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "SYSTEMROOT"]
            if key in os.environ
        }
        environment["PYTHONUNBUFFERED"] = "1"
        self.process = await asyncio.create_subprocess_exec(
            binding.python if binding else sys.executable,
            "-m",
            "eyes.runner.worker",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
            env=environment,
            limit=self.config.max_message_bytes + 1024,
        )
        self.reader = asyncio.create_task(self._read())
        await self._send(init)
        await asyncio.wait_for(self.ready, self.config.cleanup_timeout_seconds)

    async def _send(self, value):
        data = json_bytes(value)
        if len(data) > self.config.max_message_bytes:
            raise WorkerError("worker command exceeds message byte limit")
        async with self.write_lock:
            self.process.stdin.write(data + b"\n")
            await self.process.stdin.drain()

    async def _read(self):
        import json

        try:
            while line := await self.process.stdout.readline():
                value = json.loads(line)
                if value.get("ready"):
                    if not self.ready.done():
                        self.ready.set_result(True)
                elif value.get("operation_id"):
                    task = asyncio.create_task(self.operation(value["operation_id"]))
                    self.operations.add(task)
                    task.add_done_callback(self.operations.discard)
                elif value.get("id") in self.pending:
                    future = self.pending[value["id"]]
                    if not future.done():
                        if "error" in value:
                            future.set_exception(WorkerError(value["error"]))
                        else:
                            future.set_result(value.get("result"))
        except Exception as error:
            failure = WorkerError(f"worker protocol failed: {type(error).__name__}")
            self._fail(failure)
        finally:
            self._fail(WorkerError("worker process exited without a response"))

    def _fail(self, error):
        for future in [self.ready, *self.pending.values()]:
            if future is not None and not future.done():
                future.set_exception(error)

    async def call(self, phase, timeout):
        identifier = str(uuid4())
        future = asyncio.get_running_loop().create_future()
        self.pending[identifier] = future
        try:
            await self._send({"id": identifier, "phase": phase})
            return await asyncio.wait_for(future, timeout)
        finally:
            self.pending.pop(identifier, None)

    async def stop(self):
        if self.process is None:
            return True
        if self.stop_confirmed is not None:
            return self.stop_confirmed
        group = self.process.pid
        for sig, timeout in [
            (signal.SIGTERM, self.config.stop_grace_seconds),
            (signal.SIGKILL, self.config.stop_grace_seconds),
        ]:
            try:
                os.killpg(group, sig)
            except ProcessLookupError:
                break
            try:
                await asyncio.wait_for(self.process.wait(), timeout)
            except TimeoutError:
                pass
        # A child may survive its leader. Do not equate leader exit with group stop.
        try:
            os.killpg(group, 0)
            confirmed = False
        except ProcessLookupError:
            confirmed = True
        if self.reader:
            self.reader.cancel()
            await asyncio.gather(self.reader, return_exceptions=True)
        for task in self.operations:
            task.cancel()
        await asyncio.gather(*self.operations, return_exceptions=True)
        self.stop_confirmed = confirmed
        return confirmed
