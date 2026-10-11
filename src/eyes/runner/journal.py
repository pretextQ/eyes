"""Conservative, per-file handling of persisted Runner payloads."""

import json
import logging

from eyes.contracts.base import explicit_versions, read_stored_contract
from eyes.contracts.scorer import ScoreAssignment
from eyes.contracts.target import ExecutionInput
from eyes.contracts.work import ClaimedWork, ExecutionSubmission, ScoreSubmission
from eyes.runner.files import write_json

logger = logging.getLogger(__name__)


def corrupt(directory, path, error):
    # Keep the original bytes, capture and workspace together. This marker also
    # fences already queued submissions and reaping; it is not a completion.
    logger.error("journal_corrupt file=%s type=%s", path, type(error).__name__)
    try:
        write_json(
            directory / "corrupt.json",
            {"file": path.name, "error_type": type(error).__name__},
        )
    except OSError as failure:
        logger.error("journal_isolation_disk_error file=%s errno=%s", path, failure.errno)


def assignment(directory):
    path = directory / "assignment.json"
    work = read_stored_contract(
        ClaimedWork, json.loads(path.read_bytes()), source="runner_assignment"
    ).model_dump(mode="json")
    if directory.name != work["work_item_id"]:
        raise ValueError("assignment identity does not match its directory")
    model = ExecutionInput if work["kind"] == "execute" else ScoreAssignment
    work["payload"] = explicit_versions(model, work["payload"], source="runner_assignment_payload")
    return work


def submission(directory, work):
    model = ExecutionSubmission if work["kind"] == "execute" else ScoreSubmission
    body = explicit_versions(
        model, json.loads((directory / "result.json").read_bytes()), source="runner_result"
    )
    if body["lease_token"] != work["lease_token"]:
        raise ValueError("result lease does not match assignment")
    return body
