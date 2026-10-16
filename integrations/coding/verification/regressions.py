"""Authorized EOF/JSON-depth regressions; run only in an isolated Linux container."""

import json
import tempfile
import time
from pathlib import Path

from integrations.coding import scorer
from integrations.coding.verification.candidates import INTSUM
from integrations.coding.verification.run import verify_score, verify_unit, wait_gone


def verify_closed(label, before, after, code, expected_state, expected_detail, *, child=False):
    condition = {
        "id": label,
        "kind": "cli",
        "module": "intsum",
        "argv": [],
        "exit": code if code in {0, 2} else 0,
        "stderr": "",
        "json": {"count": 0, "sum": 0},
    }
    with tempfile.TemporaryDirectory(prefix="verify-eof-") as directory:
        root = Path(directory)
        marker = root / "pids"
        source = "import os, subprocess, sys, time\n"
        source += (
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
            if child
            else "child = None\n"
        )
        source += (
            f"open({str(marker)!r}, 'w').write(str(os.getpid()) + "
            "(' ' + str(child.pid) if child else ''))\n"
            'os.write(1, b\'{"count": 0, "sum": 0}\\n\')\n'
            f"time.sleep({before})\n"
            "os.close(1)\nos.close(2)\n"
            f"time.sleep({after})\n"
            + ("os.kill(os.getpid(), 15)\n" if code == -15 else f"os._exit({code})\n")
        )
        started = time.monotonic()
        outcome = scorer.run_condition(
            condition, {"intsum.py": source.encode()}, root, started + 10
        )
        elapsed = time.monotonic() - started
        assert outcome["state"] == expected_state and outcome["detail"] == expected_detail, outcome
        assert elapsed < 4.2, elapsed
        if expected_detail == "ok":
            assert elapsed >= before + after, elapsed
        wait_gone([int(pid) for pid in marker.read_text().split()])
        print(json.dumps({"scenario": label, **outcome, "seconds": round(elapsed, 3)}), flush=True)


def verify_closed_parent_death():
    with tempfile.TemporaryDirectory(prefix="verify-eof-parent-") as directory:
        root = Path(directory)
        marker = root / "closed"
        source = (
            "import os, time\nos.close(1)\nos.close(2)\n"
            f"open({str(marker)!r}, 'w').write(str(os.getpid()))\n"
            "time.sleep(30)\n"
        )
        condition = {"id": "closed-parent", "kind": "import", "module": "chunks"}
        with scorer.pending_condition(condition, {"chunks.py": source.encode()}, root) as process:
            end = time.monotonic() + 2
            while not marker.exists() and time.monotonic() < end:
                time.sleep(0.01)
            assert marker.exists(), "candidate never closed pipes"
            process.stdin.close()
            process.wait(timeout=2)
            assert process.returncode == 0, process.stderr.read()
            assert json.loads(process.stdout.read()) == {
                "outcome": "parent_closed",
                "passed": False,
            }
            wait_gone([int(marker.read_text())])
        print(json.dumps({"scenario": "parent-eof-after-output-eof", "reaped": True}), flush=True)


def verify_depth(label):
    deep = "'[' * 2000 + '0' + ']' * 2000"
    assert 4001 < scorer.OUTPUT_LIMIT
    case = next(c for c in scorer.catalog() if c["case_id"] == "py-int-cli-errors")
    source = INTSUM.replace(
        'print(json.dumps({"count": len(sys.argv) - 1, "sum": sum(map(int, sys.argv[1:]))}))',
        f"print({deep})",
    )
    assert source != INTSUM
    output = verify_score(label + ":deep-cli-json", case, {"intsum.py": source}, value=50)
    rows = json.loads(output.reason)["conditions"]
    assert any(row[1:] == ["fail", "behavior"] for row in rows)
    assert any(row[1:] == ["pass", "ok"] for row in rows)
    verify_score(
        label + ":invalid-cli-json",
        case,
        {"intsum.py": source.replace(f"print({deep})", "print('{')")},
        value=50,
    )
    verify_unit(
        label + ":deep-call-frame",
        f"import os\nos.write(1, ('\\nEYES_CALL_RESULT ' + {deep}).encode())\nos._exit(0)",
        "fail",
        "behavior",
    )


def main():
    for code in (0, 2, 7, -15):
        verify_closed(
            f"closed-exit-{code}",
            0.1,
            0.35,
            code,
            "pass" if code in {0, 2} else "fail",
            "ok" if code in {0, 2} else "behavior",
        )
    verify_closed("closed-timeout", 0, 30, 0, "fail", "timeout")
    # Closing pipes late must not grant a new three-second runtime allowance.
    verify_closed("closed-original-deadline", 1.8, 1.8, 0, "fail", "timeout")
    verify_closed("closed-descendant", 0, 0.35, 0, "pass", "ok", child=True)
    verify_closed_parent_death()
    verify_depth("default-json")
    # Exercise actual RecursionError with Python's recursive stdlib decoder. The
    # current C decoder accepts this depth. Redirect only the verification launcher;
    # production supervise/score and candidate execution remain the real functions.
    original = scorer.__file__
    try:
        scorer.__file__ = str(Path(__file__).with_name("python_json.py"))
        verify_depth("python-json")
    finally:
        scorer.__file__ = original
    print(json.dumps({"regressions": "complete"}), flush=True)


if __name__ == "__main__":
    main()
