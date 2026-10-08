"""Start the configured local Runner without printing its credential."""

import json
import os
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[2]
    state = root / "data" / "deta-integration"
    credential = json.loads((state / "runner-credential.json").read_text())
    os.environ["EYES_RUNNER_TOKEN"] = credential["token"]
    os.execv(
        sys.executable,
        [
            sys.executable,
            "-m",
            "eyes.runner.main",
            "--config",
            str(state / "runner.toml"),
            "run",
        ],
    )


if __name__ == "__main__":
    main()
