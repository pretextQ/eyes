"""Load the private Runner token at runtime, without exposing it to Docker config."""

import json
import os
import sys
from pathlib import Path


def main():
    state = Path("/app/data/mewcode-integration")
    os.environ["EYES_RUNNER_TOKEN"] = json.loads((state / "runner-credential.json").read_text())[
        "token"
    ]
    os.execv(
        sys.executable,
        [sys.executable, "-m", "eyes.runner.main", "--config", str(state / "runner.toml"), "run"],
    )


if __name__ == "__main__":
    main()
