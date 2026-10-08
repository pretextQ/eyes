"""Publish this small coding dataset and create a real Deta experiment via Eyes API."""

import argparse
import json
import os
import subprocess
from pathlib import Path
from uuid import uuid4

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=Path("data/deta-integration"))
    parser.add_argument("--server", default="http://127.0.0.1:8001")
    parser.add_argument("--deta-root", type=Path, default=Path("../deta"))
    args = parser.parse_args()
    credentials = json.loads((args.state_dir / "manage.json").read_text())
    plugins = json.loads((args.state_dir / "plugins.json").read_text())
    version = subprocess.check_output(
        ["git", "-C", str(args.deta_root), "rev-parse", "HEAD"], text=True
    ).strip()
    target = {
        "schema_version": "1.0",
        "name": "Deta coding agent",
        "external_version": version,
        "capabilities": {
            "schema_version": "1.0",
            "adapter": "python",
            "session_isolation": True,
            "environment_isolation": False,
            "cancellation": False,
            "idempotency": False,
            "reconciliation": False,
            "observation": ["task", "sdk"],
        },
        "config": {
            "agent": "deta",
            "parameters": {
                "model": os.environ["OPENAI_MODEL"],
                "base_url": os.environ["OPENAI_BASE_URL"],
                "context_window": int(os.environ["OPENAI_CONTEXT_WINDOW"]),
                "thinking": "disabled",
            },
        },
        "secret_refs": {"model": "env:OPENAI_API_KEY"},
        "concurrency_limit": 1,
    }
    scorer = {
        "schema_version": "1.0",
        "name": "Deta frozen-code acceptance",
        "plugin": "deta_code",
        "implementation_digest": plugins["scorers"]["deta_code"]["implementation_digest"],
        "required_evidence": ["output", "events", "artifacts", "sealed"],
        "timeout_seconds": 40,
    }
    with httpx.Client(
        base_url=args.server,
        timeout=30,
        headers={"Authorization": "Bearer " + credentials["token"]},
    ) as client:

        def post(path, body, **kwargs):
            response = client.post(path, json=body, **kwargs)
            response.raise_for_status()
            return response.json()

        published_target = post("/v1/targets", target)
        published_scorer = post("/v1/scorers", scorer)
        dataset = post(
            "/v1/datasets/import",
            {
                "schema_version": "1.0",
                "name": "Deta coding smoke v1 (3 tasks)",
                "jsonl": Path(__file__).with_name("coding-smoke.jsonl").read_text(),
            },
        )
        experiment = post(
            "/v1/experiments",
            {
                "schema_version": "1.0",
                "target_version_id": published_target["id"],
                "dataset_version_id": dataset["id"],
                "scorer_version_ids": [published_scorer["id"]],
                "concurrency": 1,
                "timeout_seconds": 300,
                "evidence_wait_seconds": 15,
            },
            headers={"Idempotency-Key": str(uuid4())},
        )
    result = {
        "project_id": credentials["project_id"],
        "target_id": published_target["id"],
        "dataset_id": dataset["id"],
        "scorer_id": published_scorer["id"],
        "experiment_id": experiment["id"],
        "deta_commit": version,
    }
    path = args.state_dir / ("experiment-" + experiment["id"] + ".json")
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
