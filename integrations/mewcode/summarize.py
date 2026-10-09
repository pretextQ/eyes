"""Summarize downloaded execution, scoring and capture facts without changing them."""

import json
from collections import Counter
from pathlib import Path

STATE = Path(__file__).resolve().parents[2] / "data/mewcode-integration"


def main():
    runs = json.loads((STATE / "case-runs.json").read_text(encoding="utf-8"))
    cases, event_types, usage = [], Counter(), Counter()
    for run in runs["items"]:
        for attempt in run["attempts"]:
            directory = STATE / "evidence" / run["case"]["case_id"] / attempt["id"]
            events = json.loads((directory / "events.json").read_text(encoding="utf-8"))
            types = Counter(e["content"]["type"] for e in events)
            event_types.update(types)
            output = attempt["result"]["output"]
            usage.update({k: output[k] for k in ("input_tokens", "output_tokens")})
            spans = [
                e["content"]["data"]
                for e in events
                if e["content"]["type"] == "span" and e["content"]["data"]["name"] == "mewcode.run"
            ]
            cases.append(
                {
                    "case": run["case"]["case_id"],
                    "attempt_id": attempt["id"],
                    "status": attempt["status"],
                    "cleanup_status": attempt["cleanup_status"],
                    "evidence_status": attempt["evidence_status"],
                    "evidence_details": attempt["result"].get("evidence_details"),
                    "dropped_events": attempt["result"]["dropped_events"],
                    "events": len(events),
                    "event_types": dict(types),
                    "agent_seconds": sum((s["end_ns"] - s["start_ns"]) / 1e9 for s in spans),
                    "scores": [s["result"] for s in attempt["score_runs"]],
                }
            )
    summary = {
        "cases": cases,
        "event_count": sum(event_types.values()),
        "event_types": dict(event_types),
        "usage": dict(usage),
    }
    (STATE / "acceptance.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "event_count": summary["event_count"],
                "event_types": dict(event_types),
                "usage": dict(usage),
                "cases": [
                    {k: c[k] for k in ("case", "agent_seconds", "evidence_status")} for c in cases
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
