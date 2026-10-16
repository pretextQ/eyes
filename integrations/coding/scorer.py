"""Trusted, Linux-only coding scorer; subprocess modes do not import Eyes."""

import copy
import ctypes
import hashlib
import importlib
import json
import math
import os
import runpy
import selectors
import signal
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

DATASET = Path(__file__).with_name("coding-regression.jsonl")
OUTPUT_LIMIT = 65536
SOURCE_LIMIT = 262144
PROCESS_SECONDS = 3
RECYCLE_SECONDS = 0.5
PARALLEL = 4
PHASE_SECONDS = 60
RESERVE_SECONDS = 10
MAX_UNITS = 52
SEMANTICS = dict(minimum=0, maximum=100, direction="higher", threshold=100, aggregation="mean")


def strict_json(text):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("nonfinite JSON")

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def equal(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            equal(a, b) for a, b in zip(actual, expected, strict=True)
        )
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            equal(actual[k], v) for k, v in expected.items()
        )
    return actual == expected


def catalog():
    return [strict_json(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line]


def validate_case(case):
    """Validate frozen product acceptance data, without loading candidate code."""
    allowed = {
        "py-chunk-sequence": ["chunks.py"],
        "py-int-cli-errors": ["intsum.py"],
    }
    names = allowed[case["case_id"]]
    if case["artifact_requirements"] != names or sorted(case["input"]["files"]) != sorted(names):
        raise ValueError("unexpected project paths")
    if case["environment"] or case["steps"] or case["schema_version"] != "1.0":
        raise ValueError("unsupported case envelope")
    expected = case["expectations"]
    if expected["artifacts"] != names:
        raise ValueError("artifact matrix mismatch")
    groups = expected["checks"]
    if sum(g["points"] for g in groups) != 100:
        raise ValueError("points must total 100")
    ids = []
    units = 0
    for group in groups:
        ids.append(group["id"])
        if type(group["points"]) is not int or group["points"] <= 0:
            raise ValueError("invalid weight")
        if not group["conditions"]:
            raise ValueError("empty group")
        for condition in group["conditions"]:
            ids.append(condition["id"])
            if condition["kind"] not in {"call", "import", "cli"}:
                raise ValueError("unknown condition kind")
            if condition["module"] + ".py" not in names:
                raise ValueError("unknown module")
            if condition["kind"] == "call":
                if not isinstance(condition["args"], list) or (
                    ("returns" in condition) == ("raises" in condition)
                ):
                    raise ValueError("invalid function check")
                if condition.get("raises") not in {None, "TypeError", "ValueError"}:
                    raise ValueError("invalid expected exception")
            if condition["kind"] == "cli":
                if not all(isinstance(arg, str) for arg in condition["argv"]):
                    raise ValueError("invalid argv")
                if condition["exit"] not in {0, 2} or not isinstance(condition["stderr"], str):
                    raise ValueError("invalid CLI protocol")
                if ("json" in condition) == ("stdout" in condition):
                    raise ValueError("ambiguous CLI output")
        units += len(group["conditions"])
    if len(ids) != len(set(ids)) or units > MAX_UNITS:
        raise ValueError("duplicate IDs or process budget exceeded")
    # Four concurrent lanes, 3s runtime + .5s cleanup + .5s startup allowance.
    if math.ceil(units / PARALLEL) * 4 > PHASE_SECONDS - 5:
        raise ValueError("worst-case process budget exceeds phase budget")
    return units


def check_call(condition):
    module = importlib.import_module(condition["module"])
    function = getattr(module, condition["function"])
    args = condition["args"]
    if condition.get("tuple_items"):
        args[0] = tuple(args[0])
    before = copy.deepcopy(args)
    try:
        result = function(*args)
    except Exception as error:
        return type(error).__name__ == condition.get("raises") and equal(args, before)
    if "raises" in condition:
        return False
    passed = equal(result, condition["returns"]) and equal(args, before)
    if condition.get("containers"):
        passed = (
            passed
            and result is not args[0]
            and all(part is not args[0] for part in result)
            and len({id(part) for part in result}) == len(result)
        )
        if passed and result:
            others = copy.deepcopy(result[1:])
            result[0].append("changed")
            passed = equal(args, before) and equal(result[1:], others)
    return passed


def candidate(spec):
    # All checker standard-library dependencies are imported before this boundary.
    Path(spec["ready_path"]).touch()
    sys.path.insert(0, spec["project"])
    sys.dont_write_bytecode = True
    condition = spec["condition"]
    sys.argv = [condition["module"] + ".py", "invalid argument"]
    if condition["kind"] == "cli":
        sys.argv = [condition["module"] + ".py", *condition["argv"]]
        runpy.run_module(condition["module"], run_name="__main__", alter_sys=True)
        return
    try:
        if condition["kind"] == "import":
            importlib.import_module(condition["module"])
            passed = True
        else:
            passed = check_call(condition)
    except BaseException:
        passed = False
    print(json.dumps({"passed": passed}))


def limits():
    import resource

    for key, value in (
        (resource.RLIMIT_CPU, 45),
        (resource.RLIMIT_AS, 536870912),
        (resource.RLIMIT_FSIZE, 1048576),
    ):
        _, hard = resource.getrlimit(key)
        resource.setrlimit(
            key, (min(value, hard) if hard != resource.RLIM_INFINITY else value, hard)
        )


def supervise(spec):
    """Survive worker group death; control pipe EOF always triggers candidate cleanup."""
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # Linux PR_SET_CHILD_SUBREAPER
        raise OSError("subreaper unavailable")
    selector = selectors.DefaultSelector()
    selector.register(sys.stdin.buffer, selectors.EVENT_READ, "control")
    command = [sys.executable, "-I", str(Path(__file__).resolve()), "candidate", spec["spec_path"]]
    process = None
    output = {"stdout": bytearray(), "stderr": bytearray()}
    outcome = "exited"
    try:
        process = subprocess.Popen(
            command,
            cwd=spec["project"],
            env={"PATH": os.defpath, "HOME": spec["project"]},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            preexec_fn=limits,
        )
        for name in output:
            selector.register(getattr(process, name), selectors.EVENT_READ, name)
        end = time.monotonic() + PROCESS_SECONDS
        while len(selector.get_map()) > 1:
            if time.monotonic() >= end:
                outcome = "timeout"
                break
            for key, _ in selector.select(min(0.05, max(0, end - time.monotonic()))):
                data = os.read(key.fd, 8192)
                if key.data == "control":
                    outcome = "parent_closed"
                    break
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                buffer = output[key.data]
                buffer.extend(data[: OUTPUT_LIMIT + 1 - len(buffer)])
                if len(buffer) > OUTPUT_LIMIT:
                    outcome = "output_limit"
                    break
            if outcome != "exited":
                break
    finally:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=RECYCLE_SECONDS)
            end = time.monotonic() + RECYCLE_SECONDS
            while True:
                try:
                    pid, _ = os.waitpid(-1, os.WNOHANG)
                except ChildProcessError:
                    break
                if not pid:
                    if time.monotonic() >= end:
                        raise RuntimeError("candidate descendants not reaped")
                    time.sleep(0.01)
        selector.close()
    passed = False
    if not Path(spec["ready_path"]).exists():
        raise RuntimeError("trusted launcher did not become ready")
    if outcome == "exited":
        try:
            condition = spec["condition"]
            stdout = output["stdout"].decode("utf-8")
            stderr = output["stderr"].decode("utf-8")
            if condition["kind"] == "cli":
                passed = process.returncode == condition["exit"] and stderr == condition["stderr"]
                passed = passed and (
                    equal(strict_json(stdout), condition["json"])
                    if "json" in condition
                    else stdout == condition["stdout"]
                )
            else:
                passed = (
                    process.returncode == 0
                    and not stderr
                    and equal(strict_json(stdout), {"passed": True})
                )
        except ValueError, UnicodeError:
            pass
    print(json.dumps({"outcome": outcome, "passed": passed}))


def run_condition(condition, sources, workspace, end):
    if time.monotonic() + 4 > end:
        return {"id": condition["id"], "state": "not_run"}
    with tempfile.TemporaryDirectory(prefix="coding-", dir=workspace) as directory:
        root = Path(directory)
        project = root / "project"
        project.mkdir()
        for name, content in sources.items():
            (project / name).write_bytes(content)
        spec = {
            "project": str(project),
            "condition": condition,
            "spec_path": str(root / "unit.json"),
            "ready_path": str(root / "ready"),
        }
        (root / "unit.json").write_text(json.dumps(spec), encoding="utf-8")
        command = [
            sys.executable,
            "-I",
            str(Path(__file__).resolve()),
            "supervise",
            spec["spec_path"],
        ]
        # Never inherit model credentials, worker token, or unrelated host environment.
        process = subprocess.Popen(
            command,
            cwd=root,
            env={"PATH": os.defpath, "HOME": str(root)},
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            # Keep stdin open until the supervisor has killed/reaped every candidate child.
            process.wait(timeout=min(4.5, max(0.1, end - time.monotonic())))
            stdout = process.stdout.read(OUTPUT_LIMIT * 16)
            if process.returncode:
                raise RuntimeError("supervisor failed")
            actual = strict_json(stdout)
        except BaseException:
            process.stdin.close()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired as error:
                raise RuntimeError("supervisor cleanup unconfirmed") from error
            raise
        finally:
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()
        passed = actual["passed"]
        diagnostic = actual["outcome"]
        if actual["outcome"] == "exited":
            diagnostic = "ok" if passed else "behavior"
        return {"id": condition["id"], "state": "pass" if passed else "fail", "detail": diagnostic}


def score(request, context):
    from eyes.contracts.scorer import ScoreOutput

    refs = []
    outcomes = []
    groups = []

    def result(status, detail, value=None):
        reason = json.dumps(
            {"detail": detail, "groups": groups, "conditions": outcomes}, separators=(",", ":")
        )
        if len(reason) > 5000:
            return ScoreOutput(
                schema_version="1.0", status="error", reason="diagnostic budget exceeded"
            )
        return ScoreOutput(
            schema_version="1.0",
            status=status,
            reason=reason,
            evidence_refs=refs,
            value=value,
            verdict=("pass" if value == 100 else "fail") if status == "completed" else None,
        )

    try:
        if sys.platform != "linux":
            raise ValueError("Linux scorer required")
        canonical = next(c for c in catalog() if c["case_id"] == request.case["case_id"])
        validate_case(canonical)
        if any(request.case.get(key) != value for key, value in canonical.items()):
            raise ValueError("case differs from installed dataset")
        if (
            request.scorer.numeric is None
            or any(
                getattr(request.scorer.numeric, key) != value for key, value in SEMANTICS.items()
            )
            or request.scorer.required_evidence != ["input"]
            or request.scorer.timeout_seconds < 120
        ):
            raise ValueError("scorer semantics or timeout mismatch")
        if request.scorer.config != {
            "dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest()
        }:
            raise ValueError("dataset digest mismatch")
        checks = canonical["expectations"]["checks"]
        conditions = [c for group in checks for c in group["conditions"]]
        outcomes = [{"id": c["id"], "state": "not_run"} for c in conditions]
        sources = {}
        for name in canonical["artifact_requirements"]:
            matches = [
                a
                for a in request.evidence.artifacts
                if str(a.get("metadata_content", {}).get("name", "")).casefold() == name.casefold()
            ]
            if len(matches) != 1 or request.evidence.status in {"unavailable", "expired"}:
                return result("insufficient_evidence", "missing, ambiguous or unavailable code")
            artifact = matches[0]
            if artifact["metadata_content"]["name"] != name:
                return result("insufficient_evidence", "ambiguous code path")
            ref = "artifact:" + str(artifact["id"])
            if ref not in request.evidence.references:
                raise ValueError("artifact reference unavailable")
            refs.append(ref)
            metadata = artifact["metadata_content"]
            with context.artifact(str(artifact["id"])).open("rb") as stream:
                content = stream.read(SOURCE_LIMIT + 1)
            if (
                len(content) > SOURCE_LIMIT
                or len(content) != metadata["size"]
                or hashlib.sha256(content).hexdigest() != metadata["sha256"]
            ):
                raise ValueError("code size or integrity failure")
            sources[name] = content
        refs.extend(r for r in request.evidence.references if r.endswith(":expectations"))
        remaining = PHASE_SECONDS
        if request.deadline:
            remaining = min(
                remaining, (request.deadline - datetime.now(UTC)).total_seconds() - RESERVE_SECONDS
            )
        end = time.monotonic() + remaining
        with ThreadPoolExecutor(max_workers=PARALLEL) as executor:
            futures = [
                executor.submit(run_condition, c, sources, context.workspace, end)
                for c in conditions
            ]
            broken = False
            for index, future in enumerate(futures):
                try:
                    outcomes[index] = future.result()
                except Exception as error:
                    broken = True
                    outcomes[index] = {
                        "id": conditions[index]["id"],
                        "state": "error",
                        "detail": type(error).__name__,
                    }
        if broken:
            return result("error", "infrastructure check failure")
        if any(o["state"] == "not_run" for o in outcomes) or time.monotonic() > end:
            return result("error", "plugin phase budget exhausted")
        by_id = {o["id"]: o for o in outcomes}
        value = 0
        for group in checks:
            earned = (
                group["points"]
                if all(by_id[c["id"]]["state"] == "pass" for c in group["conditions"])
                else 0
            )
            value += earned
            groups.append({"id": group["id"], "earned": earned, "points": group["points"]})
        return result("completed", "frozen acceptance checks", value)
    except Exception as error:
        # Do not include untrusted exception messages, paths, output or credentials.
        return result("error", "infrastructure:" + type(error).__name__)


if __name__ == "__main__":
    spec = strict_json(Path(sys.argv[2]).read_text(encoding="utf-8"))
    {"candidate": candidate, "supervise": supervise}[sys.argv[1]](spec)
