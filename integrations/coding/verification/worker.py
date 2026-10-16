"""Exercise the actual ProcessWorker score boundary, without a platform or Agent."""

import asyncio
import json
import os
import signal
import tempfile
import time
from pathlib import Path

from eyes.contracts.scorer import ScoreOutput
from eyes.runner.config import Binding, RunnerConfig
from eyes.runner.process import ProcessWorker, WorkerError
from integrations.coding import scorer
from integrations.coding.verification.candidates import CORRECT
from integrations.coding.verification.run import make_request, wait_gone


async def verify(case, *, kill=False):
    with tempfile.TemporaryDirectory(prefix="verify-worker-") as directory:
        root = Path(directory)
        sources = CORRECT[case["case_id"]]
        if kill:
            source = """import os, pathlib, subprocess, sys, time
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
marker = pathlib.Path(PID_ROOT, 'pids-' + str(os.getpid()))
marker.write_text(str(os.getpid()) + ' ' + str(child.pid))
time.sleep(30)
""".replace("PID_ROOT", repr(directory))
            sources = {name: source for name in sources}
        request, _ = make_request(root, case, sources)
        payload = root / "score.json"
        payload.write_text(request.model_dump_json())
        binding = Binding(
            entry_point="integrations.coding.scorer:score",
            import_paths=[Path("/work"), Path("/work/src")],
            cpu_seconds=45,
            memory_bytes=536870912,
            file_bytes=1048576,
        )
        config = RunnerConfig(state_dir=root / "unused-state", stop_grace_seconds=1)
        worker = ProcessWorker(config, lambda value: asyncio.sleep(0))
        started = time.monotonic()
        task = None
        try:
            await worker.start(
                {
                    "kind": "score",
                    "config": config.model_dump(mode="json"),
                    "binding": binding.model_dump(mode="json"),
                    "workspace": directory,
                    "evidence_dir": str(root / "worker-evidence"),
                    "secrets": {},
                    "payload_path": str(payload),
                    "max_payload_bytes": config.max_score_input_bytes,
                    "artifact_ids": [a["id"] for a in request.evidence.artifacts],
                },
                binding,
            )
            task = asyncio.create_task(worker.call("score", 120))
            if kill:
                end = time.monotonic() + 5
                while not list(root.glob("pids-*")) and time.monotonic() < end:
                    await asyncio.sleep(0.02)
                assert list(root.glob("pids-*")), "candidate never started"
                supervisors = [
                    int(pid)
                    for path in Path(f"/proc/{worker.process.pid}/task").glob("*/children")
                    for pid in path.read_text().split()
                ]
                assert supervisors, "did not identify independent supervisors"
                os.killpg(worker.process.pid, signal.SIGKILL)
                try:
                    await task
                except WorkerError:
                    pass
                else:
                    raise AssertionError("killed worker unexpectedly completed")
                await asyncio.sleep(0.2)
                pids = supervisors + [
                    int(pid) for path in root.glob("pids-*") for pid in path.read_text().split()
                ]
                wait_gone(pids)
                print(
                    json.dumps(
                        {"scenario": "actual-worker-sigkill", "reaped_processes": len(pids)}
                    ),
                    flush=True,
                )
            else:
                result = ScoreOutput.model_validate(await task)
                assert result.status == "completed" and result.value == 100, result
                await worker.call("close", 10)
                print(
                    json.dumps(
                        {
                            "scenario": "actual-worker:" + case["case_id"],
                            "value": result.value,
                            "seconds": round(time.monotonic() - started, 3),
                        }
                    ),
                    flush=True,
                )
        finally:
            assert await worker.stop(), "actual worker group stop unconfirmed"
            if task:
                await asyncio.gather(task, return_exceptions=True)


async def main():
    cases = scorer.catalog()
    for case in cases:
        await verify(case)
    await verify(cases[0], kill=True)
    print(json.dumps({"actual_worker_verification": "complete"}), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
