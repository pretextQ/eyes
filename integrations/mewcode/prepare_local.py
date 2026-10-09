"""Prepare ignored local configuration; never print resolved credentials."""

import hashlib
import json
import os
import secrets
import subprocess
from pathlib import Path

from mewcode.config import load_config

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "data/mewcode-integration"
MEWCODE = ROOT.parent / "MewCode"


def main():
    STATE.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        subprocess.run(
            [
                "icacls",
                str(STATE),
                "/inheritance:r",
                "/grant:r",
                os.environ["USERNAME"] + ":(OI)(CI)F",
            ],
            check=True,
            capture_output=True,
        )
    else:
        STATE.chmod(0o700)
    config = load_config(MEWCODE / ".mewcode/config.yaml")
    provider = next(p for p in config.providers if p.protocol == "openai-compat")
    key = provider.resolve_api_key()
    if not key or "\n" in key:
        raise ValueError("usable model credential required")
    credential = STATE / "model.env"
    credential.write_text("MEWCODE_MODEL_KEY=" + key + "\n", encoding="utf-8")
    provider_snapshot = {
        "name": provider.name,
        "protocol": provider.protocol,
        "base_url": provider.base_url,
        "model": provider.model,
        "thinking": provider.thinking,
        "context_window": provider.get_context_window(),
        "max_output_tokens": provider.get_max_output_tokens(),
    }
    (STATE / "parameters.json").write_text(
        json.dumps(
            {"provider": provider_snapshot, "permission_mode": "dontAsk", "max_iterations": 12},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    compose_env = STATE / "compose.env"
    if not compose_env.exists():
        compose_env.write_text(
            "POSTGRES_PASSWORD="
            + secrets.token_hex(32)
            + "\nEYES_POSTGRES_PORT=55435\nEYES_API_PORT=18044\nEYES_WEB_PORT=18081\n"
            + "EYES_CONTROL_IMAGE=eyes-mewcode:local\n",
            encoding="utf-8",
        )
    (STATE / "runner.toml").write_bytes(
        (ROOT / "integrations/mewcode/runner.example.toml").read_bytes()
    )
    versions = {}
    for name, path, source in [
        ("eyes", ROOT, ROOT / "src"),
        ("mewcode", MEWCODE, MEWCODE / "mewcode"),
    ]:
        files = {
            str(p.relative_to(path)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(source.rglob("*.py"))
        }
        versions[name] = {
            "commit": subprocess.check_output(
                ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
            ).strip(),
            "status": subprocess.check_output(
                ["git", "-C", str(path), "status", "--short"], text=True
            ),
            "source_sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
            "source_files": files,
        }
    (STATE / "versions.json").write_text(json.dumps(versions, indent=2) + "\n", encoding="utf-8")
    print("Local model and deployment configuration prepared; credentials omitted.")


if __name__ == "__main__":
    main()
