"""Start a local control component using private ignored configuration."""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


def main():
    load_dotenv(ROOT / "data/mewcode-integration/control.env")
    if sys.argv[1] == "scheduler":
        from eyes.server.scheduling.worker import main as scheduler

        sys.argv = [sys.argv[0]]
        scheduler()
    elif sys.argv[1] == "web":
        os.environ["EYES_API_PROXY_TARGET"] = "http://127.0.0.1:18044"
        subprocess.run(
            [
                "node",
                str(ROOT / "frontend/node_modules/vite/bin/vite.js"),
                "--host",
                "127.0.0.1",
                "--port",
                "18081",
                "--strictPort",
            ],
            cwd=ROOT / "frontend",
            check=True,
        )
    else:
        raise ValueError("expected scheduler or web")


if __name__ == "__main__":
    main()
