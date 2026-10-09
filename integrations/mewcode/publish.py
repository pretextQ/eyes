"""Publish the existing dataset and scorer through Eyes' public API."""

import json
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "data/mewcode-integration"


def main():
    credentials = json.loads((STATE / "manage.json").read_text())
    plugins = json.loads((STATE / "plugins.json").read_text())
    versions = json.loads((STATE / "versions.json").read_text())
    parameters = json.loads((STATE / "parameters.json").read_text())
    version = versions["mewcode"]
    target = {
        "name": "MewCode coding agent",
        "external_version": version["commit"] + ":sha256:" + version["source_sha256"],
        "capabilities": {
            "adapter": "python",
            "session_isolation": True,
            "environment_isolation": False,
            "cancellation": False,
            "idempotency": False,
            "reconciliation": False,
            "observation": ["task", "sdk"],
        },
        "config": {"agent": "mewcode", "parameters": parameters},
        "secret_refs": {"model": "env:MEWCODE_MODEL_KEY"},
        "concurrency_limit": 1,
    }
    scorer = {
        "name": "Existing frozen-code acceptance",
        "plugin": "deta_code",
        "implementation_digest": plugins["scorers"]["deta_code"]["implementation_digest"],
        "required_evidence": ["output", "events", "artifacts", "sealed"],
        "timeout_seconds": 40,
    }
    key_path = STATE / "create-idempotency-key.txt"
    if not key_path.exists():
        key_path.write_text(str(uuid4()), encoding="utf-8")
    with httpx.Client(
        base_url="http://127.0.0.1:18044",
        timeout=30,
        headers={"Authorization": "Bearer " + credentials["token"]},
    ) as client:

        def post(path, body, **kwargs):
            response = client.post(path, json=body, **kwargs)
            response.raise_for_status()
            return response.json()

        catalog_path = STATE / "published.json"
        if catalog_path.exists():
            catalog = json.loads(catalog_path.read_text())
        else:
            catalog = {
                "target": post("/v1/targets", target),
                "scorer": post("/v1/scorers", scorer),
                "dataset": post(
                    "/v1/datasets/import",
                    {
                        "name": "Existing Deta coding smoke (3 tasks)",
                        "jsonl": (ROOT / "integrations/deta/coding-smoke.jsonl").read_text(
                            encoding="utf-8"
                        ),
                    },
                ),
            }
            catalog_path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
        experiment = post(
            "/v1/experiments",
            {
                "target_version_id": catalog["target"]["id"],
                "dataset_version_id": catalog["dataset"]["id"],
                "scorer_version_ids": [catalog["scorer"]["id"]],
                "concurrency": 1,
                "timeout_seconds": 300,
                "evidence_wait_seconds": 15,
            },
            headers={"Idempotency-Key": key_path.read_text()},
        )
    result = {
        "project_id": credentials["project_id"],
        "target_id": catalog["target"]["id"],
        "dataset_id": catalog["dataset"]["id"],
        "scorer_id": catalog["scorer"]["id"],
        "experiment_id": experiment["id"],
    }
    (STATE / "experiment.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
