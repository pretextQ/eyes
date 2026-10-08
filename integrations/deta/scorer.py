"""Execute frozen Python artifacts against the coding dataset's acceptance inputs."""

import json
import os
import signal
import subprocess
import sys

from eyes.contracts.scorer import ScoreOutput

INVOKE = """
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location('submission', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
call = json.loads(sys.argv[2])
try:
    result = getattr(module, call['function'])(*call['args'])
except Exception as error:
    print(json.dumps({'raises': type(error).__name__}))
else:
    print(json.dumps({'returns': result}, ensure_ascii=False))
"""


def run(command, workspace):
    process = subprocess.Popen(
        command,
        cwd=workspace,
        env={"PATH": os.defpath, "HOME": str(workspace)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=5)
        return {"exit_code": process.returncode, "stdout": stdout, "stderr": stderr}
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def score(request, context):
    expectations = request.case["expectations"]
    name = expectations["artifact"]
    artifact = next(
        (a for a in request.evidence.artifacts if a["metadata_content"]["name"] == name), None
    )
    if artifact is None:
        missing = any(
            e.get("type") == "artifact.missing" and e.get("data", {}).get("name") == name
            for e in request.evidence.events
        )
        refs = [r for r in request.evidence.references if r.startswith("event:")]
        return ScoreOutput(
            status="completed" if missing and refs else "insufficient_evidence",
            verdict="fail" if missing and refs else None,
            reason=f"Required code artifact missing: {name}",
            evidence_refs=refs,
        )
    source = context.artifact(str(artifact["id"]))
    # Materialize a .py file in the scoring workspace; evidence remains read-only.
    candidate = context.workspace / "submission.py"
    candidate.write_bytes(source.read_bytes())
    outcomes = []
    for check in expectations["checks"]:
        command = [sys.executable, "-I"]
        if "function" in check:
            command += ["-c", INVOKE, str(candidate), json.dumps(check)]
        else:
            command += [str(candidate), *check["argv"]]
        try:
            actual = run(command, context.workspace)
            if "function" in check:
                expected = {k: check[k] for k in ("returns", "raises") if k in check}
                passed = actual["exit_code"] == 0 and json.loads(actual["stdout"]) == expected
            else:
                passed = (
                    actual["exit_code"] == check.get("exit_code", 0)
                    and json.loads(actual["stdout"]) == check["json"]
                )
            outcomes.append({"pass": passed, "actual": actual})
        except (subprocess.TimeoutExpired, ValueError) as error:
            outcomes.append({"pass": False, "error": type(error).__name__})
    passed = all(item["pass"] for item in outcomes)
    return ScoreOutput(
        status="completed",
        verdict="pass" if passed else "fail",
        reason=json.dumps(
            {
                "passed": sum(item["pass"] for item in outcomes),
                "total": len(outcomes),
                "checks": outcomes,
            },
            ensure_ascii=False,
        )[:5000],
        evidence_refs=[f"artifact:{artifact['id']}"]
        + [ref for ref in request.evidence.references if ref.endswith(":expectations")],
    )
