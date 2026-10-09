"""Download real public-API results and verify artifact bytes against the manifest."""

import hashlib
import json
from pathlib import Path

import httpx

STATE = Path(__file__).resolve().parents[2] / "data/mewcode-integration"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    credentials = json.loads((STATE / "manage.json").read_text())
    experiment = json.loads((STATE / "experiment.json").read_text())
    identifier = experiment["experiment_id"]
    with httpx.Client(
        base_url="http://127.0.0.1:18044",
        timeout=30,
        headers={"Authorization": "Bearer " + credentials["token"]},
    ) as client:

        def get(path):
            response = client.get(path)
            response.raise_for_status()
            return response.json()

        results = get(f"/v1/experiments/{identifier}/results")
        runs = get(f"/v1/experiments/{identifier}/case-runs?limit=100")
        save(STATE / "results.json", results)
        save(STATE / "case-runs.json", runs)
        save(STATE / "experiment-detail.json", get(f"/v1/experiments/{identifier}"))
        save(STATE / "operations.json", get("/v1/operations"))
        checks = []
        for run in runs["items"]:
            for attempt in run["attempts"]:
                directory = STATE / "evidence" / run["case"]["case_id"] / attempt["id"]
                save(directory / "attempt.json", get(f"/v1/attempts/{attempt['id']}"))
                events = []
                while True:
                    batch = get(
                        f"/v1/attempts/{attempt['id']}/events?limit=100&offset={len(events)}"
                    )["items"]
                    events.extend(batch)
                    if len(batch) < 100:
                        break
                save(directory / "events.json", events)
                manifests = get(f"/v1/attempts/{attempt['id']}/manifests?limit=100")
                save(directory / "manifests.json", manifests)
                artifacts = {}
                for payload in (STATE / "runner/work").glob("*/payload.json"):
                    frozen = json.loads(payload.read_text(encoding="utf-8"))
                    if frozen.get("attempt_id") == attempt["id"] and "scorer" in frozen:
                        save(
                            directory / ("score-input-" + frozen["score_run_id"] + ".json"), frozen
                        )
                        artifacts.update({a["id"]: a for a in frozen["evidence"]["artifacts"]})
                for artifact in artifacts.values():
                    response = client.get(f"/v1/artifacts/{artifact['id']}/content")
                    response.raise_for_status()
                    metadata = artifact["metadata_content"]
                    digest = hashlib.sha256(response.content).hexdigest()
                    if digest != metadata["sha256"] or len(response.content) != metadata["size"]:
                        raise ValueError("downloaded artifact integrity mismatch")
                    name = Path(metadata["name"]).name
                    (directory / name).write_bytes(response.content)
                    checks.append(
                        {
                            "attempt_id": attempt["id"],
                            "artifact_id": artifact["id"],
                            "name": name,
                            "sha256": digest,
                            "size": len(response.content),
                        }
                    )
        save(STATE / "artifact-verification.json", checks)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
