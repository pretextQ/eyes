"""Offline acceptance configuration validation. Never executes candidate code."""

import hashlib
import json

from eyes.contracts.dataset import CaseDefinition
from integrations.coding.scorer import DATASET, SEMANTICS, catalog, validate_case


def main():
    cases = catalog()
    identifiers = [case["case_id"] for case in cases]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("duplicate case IDs")
    counts = {}
    for case in cases:
        CaseDefinition.model_validate(case)
        counts[case["case_id"]] = validate_case(case)
    print(
        json.dumps(
            {
                "cases": counts,
                "config": {"dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest()},
                "numeric": SEMANTICS,
                "required_evidence": ["input"],
                "timeout_seconds": 120,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
