"""Authorized offline verification; no Agent, network, platform writes or historical evidence."""

import copy
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from eyes.contracts.scorer import ScoreInput, ScoreOutput
from eyes.sdk.context import ScoreContext
from integrations.coding import scorer
from integrations.coding.verification.candidates import CHUNKS, CORRECT, INTSUM, MONEY


def make_request(root, case, sources):
    evidence = root / "evidence"
    evidence.mkdir()
    artifacts = []
    for name, source in sources.items():
        identifier = str(uuid4())
        data = source.encode("utf-8")
        (evidence / identifier).write_bytes(data)
        artifacts.append(
            {
                "id": identifier,
                "metadata_content": {
                    "name": name,
                    "size": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                },
            }
        )
    refs = ["artifact:" + a["id"] for a in artifacts] + ["case:verification:expectations"]
    request = ScoreInput.model_validate(
        {
            "schema_version": "1.0",
            "score_run_id": str(uuid4()),
            "attempt_id": str(uuid4()),
            "case": case,
            "result": {},
            "evidence": {
                "schema_version": "1.0",
                "manifest_id": str(uuid4()),
                "status": "sealed",
                "references": refs,
                "events": [],
                "artifacts": artifacts,
                "dropped_events": 0,
            },
            "scorer": {
                "schema_version": "1.0",
                "name": "offline-verification",
                "plugin": "coding_regression",
                "implementation_digest": hashlib.sha256(
                    Path(scorer.__file__).read_bytes()
                ).hexdigest(),
                "config": {
                    "dataset_sha256": hashlib.sha256(scorer.DATASET.read_bytes()).hexdigest()
                },
                "numeric": {"schema_version": "1.0", **scorer.SEMANTICS},
                "required_evidence": ["input"],
                "timeout_seconds": 120,
            },
            "traceparent": "00-" + "1" * 32 + "-" + "2" * 16 + "-01",
            "execution_trace_id": "3" * 32,
            "deadline": (datetime.now(UTC) + timedelta(seconds=120)).isoformat(),
        }
    )
    context = ScoreContext(root, None, {}, [a["id"] for a in artifacts])
    return request, context


def verify_score(label, case, sources, status="completed", value=None, change=None):
    with tempfile.TemporaryDirectory(prefix="verify-score-") as directory:
        request, context = make_request(Path(directory), copy.deepcopy(case), sources)
        if change:
            change(request, context)
        started = time.monotonic()
        output = scorer.score(request, context)
        ScoreOutput.model_validate(output.model_dump())
        assert output.status == status, (label, output)
        if status == "completed":
            assert output.value == value if value is not None else output.value < 100, (
                label,
                output,
            )
            assert output.verdict == ("pass" if value == 100 else "fail"), (label, output)
        else:
            assert output.value is None and output.verdict is None
        assert set(output.evidence_refs) <= set(request.evidence.references)
        reason = json.loads(output.reason)
        conditions = reason["conditions"]
        assert len(output.reason) <= 5000
        if conditions:
            assert [row[0] for row in conditions] == [
                c["id"] for group in case["expectations"]["checks"] for c in group["conditions"]
            ]
        if status == "completed":
            assert all(row[1] in {"pass", "fail"} for row in conditions)
            assert sum(g["earned"] for g in reason["groups"]) == output.value
        assert (
            len(conditions) == sum(len(g["conditions"]) for g in case["expectations"]["checks"])
            or status == "error"
        )
        print(
            json.dumps(
                {
                    "scenario": label,
                    "status": output.status,
                    "value": output.value,
                    "conditions": len(conditions),
                    "reason_chars": len(output.reason),
                    "seconds": round(time.monotonic() - started, 3),
                }
            ),
            flush=True,
        )
        return output


def wait_gone(pids):
    end = time.monotonic() + 3
    while time.monotonic() < end:
        if all(not Path(f"/proc/{pid}").exists() for pid in pids):
            return
        time.sleep(0.02)
    raise AssertionError(f"processes remain: {pids}")


def verify_unit(label, source, expected_state, expected_detail):
    condition = {
        "id": "unit",
        "kind": "call",
        "module": "chunks",
        "function": "chunk",
        "args": [[1, 2], 1],
        "returns": [[1], [2]],
    }
    with tempfile.TemporaryDirectory(prefix="verify-unit-") as directory:
        root = Path(directory)
        marker = root / "pids"
        source = source.replace("PID_PATH", repr(str(marker)))
        outcome = scorer.run_condition(
            condition, {"chunks.py": source.encode()}, root, time.monotonic() + 10
        )
        assert outcome["state"] == expected_state and outcome["detail"] == expected_detail, outcome
        if marker.exists():
            wait_gone([int(value) for value in marker.read_text().split()])
        print(json.dumps({"scenario": label, **outcome}), flush=True)


def verify_worker_death():
    # A real process runs the production run_condition, then is killed mid-candidate.
    with tempfile.TemporaryDirectory(prefix="verify-death-") as directory:
        root = Path(directory)
        source = """import os, subprocess, sys, time
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
with open(PID_PATH, 'w') as stream:
    stream.write(str(os.getpid()) + ' ' + str(child.pid))
time.sleep(30)
""".replace("PID_PATH", repr(str(root / "pids")))
        payload = root / "payload.json"
        payload.write_text(json.dumps({"root": str(root), "source": source}))
        worker = subprocess.Popen(
            [sys.executable, "-m", __spec__.name, "child", str(payload)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            end = time.monotonic() + 5
            while not (root / "pids").exists() and time.monotonic() < end:
                time.sleep(0.02)
            assert (root / "pids").exists(), "candidate never started"
            pids = [int(value) for value in (root / "pids").read_text().split()]
            os.killpg(worker.pid, signal.SIGKILL)
            worker.wait(timeout=3)
            wait_gone(pids)
            print(
                json.dumps({"scenario": "worker-sigkill", "candidate_and_child_reaped": True}),
                flush=True,
            )
        finally:
            if worker.poll() is None:
                os.killpg(worker.pid, signal.SIGKILL)
            worker.communicate(timeout=3)


def main():
    cases = {case["case_id"]: case for case in scorer.catalog()}
    for identifier, sources in CORRECT.items():
        verify_score("correct:" + identifier, cases[identifier], sources, value=100)
    chunk = cases["py-chunk-sequence"]
    integer = cases["py-int-cli-errors"]
    order = cases["py-order-pricing-project"]
    verify_score(
        "chunk-bool",
        chunk,
        {"chunks.py": CHUNKS.replace("type(size) is not int", "not isinstance(size, int)")},
        value=95,
    )
    verify_score(
        "chunk-mutation",
        chunk,
        {"chunks.py": CHUNKS.replace("    return [", "    items.reverse()\n    return [")},
    )
    verify_score(
        "chunk-call-output-allowed",
        chunk,
        {"chunks.py": CHUNKS.replace("    return [", "    print('debug')\n    return [")},
        value=100,
    )
    verify_score("chunk-import-whitespace", chunk, {"chunks.py": "print()\n" + CHUNKS}, value=85)
    verify_score("integer-ascii", integer, {"intsum.py": INTSUM.replace("[0-9]", r"\d")}, value=60)
    verify_score(
        "integer-error-channel",
        integer,
        {"intsum.py": INTSUM.replace("file=sys.stderr", "file=sys.stdout")},
        value=60,
    )
    verify_score(
        "integer-bool-json", integer, {"intsum.py": INTSUM.replace("len(sys.argv) - 1", "True")}
    )
    sources = dict(CORRECT[order["case_id"]])
    sources["money.py"] = MONEY.replace(" + 5000", "")
    verify_score("order-floor", order, sources)
    sources = dict(CORRECT[order["case_id"]])
    sources["main.py"] = sources["main.py"].replace("object_pairs_hook=pairs, ", "")
    verify_score("order-duplicate-keys", order, sources, value=96)
    verify_score("missing-code", chunk, {}, status="insufficient_evidence")
    verify_score(
        "untrusted-missing-event",
        chunk,
        {},
        status="insufficient_evidence",
        change=lambda r, c: r.evidence.events.append(
            {
                "type": "artifact.missing",
                "data": {"name": "chunks.py"},
                "event_id": str(uuid4()),
            }
        ),
    )
    verify_score("syntax", chunk, {"chunks.py": "def !"}, value=0)
    verify_score(
        "expired",
        chunk,
        CORRECT[chunk["case_id"]],
        status="insufficient_evidence",
        change=lambda r, c: setattr(r.evidence, "status", "expired"),
    )
    verify_score(
        "ambiguous",
        chunk,
        CORRECT[chunk["case_id"]],
        status="insufficient_evidence",
        change=lambda r, c: r.evidence.artifacts.append(copy.deepcopy(r.evidence.artifacts[0])),
    )
    verify_score(
        "integrity",
        chunk,
        CORRECT[chunk["case_id"]],
        status="error",
        change=lambda r, c: c.artifact(str(r.evidence.artifacts[0]["id"])).write_bytes(b"corrupt"),
    )
    verify_score(
        "missing-local-download",
        chunk,
        CORRECT[chunk["case_id"]],
        status="error",
        change=lambda r, c: c.artifact(str(r.evidence.artifacts[0]["id"])).unlink(),
    )
    verify_score(
        "budget",
        chunk,
        CORRECT[chunk["case_id"]],
        status="error",
        change=lambda r, c: setattr(r, "deadline", datetime.now(UTC)),
    )
    verify_score(
        "digest",
        chunk,
        CORRECT[chunk["case_id"]],
        status="error",
        change=lambda r, c: r.scorer.config.update(dataset_sha256="0" * 64),
    )
    hung_order = {name: "import time; time.sleep(30)" for name in CORRECT[order["case_id"]]}
    output = verify_score("order-all-timeouts-budget", order, hung_order, value=0)
    assert all(row[1:] == ["fail", "timeout"] for row in json.loads(output.reason)["conditions"])
    output = verify_score(
        "phase-budget-partial",
        order,
        hung_order,
        status="error",
        change=lambda r, c: setattr(r, "deadline", datetime.now(UTC) + timedelta(seconds=15)),
    )
    assert any(row[1] == "not_run" for row in json.loads(output.reason)["conditions"])
    verify_unit("timeout", "import time\ntime.sleep(30)", "fail", "timeout")
    verify_unit("stdout-limit", "import os\nos.write(1, b'x'*70000)", "fail", "output_limit")
    verify_unit("stderr-limit", "import os\nos.write(2, b'x'*70000)", "fail", "output_limit")
    spawn = """import os, subprocess, sys
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
with open(PID_PATH, 'w') as stream:
    stream.write(str(os.getpid()) + ' ' + str(child.pid))
"""
    verify_unit("success-descendant", spawn + CHUNKS, "pass", "ok")
    verify_unit("exception-descendant", spawn + "raise ValueError", "fail", "behavior")
    verify_unit("timeout-descendant", spawn + "import time; time.sleep(30)", "fail", "timeout")
    verify_unit("output-descendant", spawn + "os.write(1, b'x'*70000)", "fail", "output_limit")
    verify_unit(
        "candidate-resource-limits",
        "import resource\n"
        "assert resource.getrlimit(resource.RLIMIT_CPU)[0] == 45\n"
        "assert resource.getrlimit(resource.RLIMIT_AS)[0] == 536870912\n"
        "assert resource.getrlimit(resource.RLIMIT_FSIZE)[0] == 1048576\n" + CHUNKS,
        "pass",
        "ok",
    )
    verify_worker_death()
    print(json.dumps({"verification": "complete"}), flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "child":
        payload = json.loads(Path(sys.argv[2]).read_text())
        scorer.run_condition(
            {"id": "death", "kind": "import", "module": "chunks"},
            {"chunks.py": payload["source"].encode()},
            Path(payload["root"]),
            time.monotonic() + 10,
        )
    else:
        main()
