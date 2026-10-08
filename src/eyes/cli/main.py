import argparse
import json
import os
import sys
import time
from pathlib import Path
from uuid import UUID

import httpx

from eyes.contracts.comparison import ComparisonCreate
from eyes.contracts.dataset import DatasetImport
from eyes.contracts.target import http_origin
from eyes.contracts.work import ExperimentBatchCreate, ExperimentCreate

EXIT = {"pass": 0, "fail": 1, "inconclusive": 2}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(3, '{"error":"invalid_command_arguments"}\n')


def main():
    parser = Parser(description="Eyes public API and CI client (JSON output)")
    parser.add_argument("--url", default=os.environ.get("EYES_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--token-env", default="EYES_TOKEN")
    parser.add_argument("--timeout", type=float, default=30)
    commands = parser.add_subparsers(dest="command", required=True)
    dataset = commands.add_parser("import-dataset")
    dataset.add_argument("--name", required=True)
    dataset.add_argument("--file", type=Path, required=True)
    for name in ("create", "create-batch", "compare"):
        command = commands.add_parser(name)
        command.add_argument("--file", type=Path, required=True)
        command.add_argument(
            "--key", required=True, help="stable idempotency key; reuse on transport retry"
        )
    for name in (
        "get",
        "results",
        "cancel",
        "report",
        "gate",
        "wait",
        "retry-score",
        "rescore",
        "batch",
        "cancel-batch",
        "wait-batch",
    ):
        command = commands.add_parser(name)
        command.add_argument("id", type=UUID)
        if name in {"wait", "wait-batch"}:
            command.add_argument("--deadline", type=float, default=600)
            command.add_argument("--interval", type=float, default=2)
    for name in ("list", "batches"):
        listing = commands.add_parser(name)
        listing.add_argument("--limit", type=int, default=50)
        listing.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()
    try:
        http_origin(args.url)
        if args.timeout <= 0:
            raise ValueError("timeout must be positive")
        token = os.environ.get(args.token_env)
        if not token:
            raise ValueError(f"set credential in {args.token_env}")
        with httpx.Client(
            base_url=args.url.rstrip("/") + "/",
            timeout=args.timeout,
            headers={"Authorization": f"Bearer {token}"},
            follow_redirects=False,
            trust_env=False,
        ) as client:
            path, method, payload, headers = "v1/experiments", "GET", None, {}
            if args.command == "import-dataset":
                path, method = "v1/datasets/import", "POST"
                payload = DatasetImport(name=args.name, jsonl=args.file.read_text()).model_dump(
                    mode="json"
                )
            elif args.command in {"create", "create-batch", "compare"}:
                model, path = {
                    "create": (ExperimentCreate, "v1/experiments"),
                    "create-batch": (ExperimentBatchCreate, "v1/experiment-batches"),
                    "compare": (ComparisonCreate, "v1/comparisons"),
                }[args.command]
                # Let the API distinguish omitted defaults from explicit settings
                # when replaying requests created before a protocol extension.
                payload = model.model_validate_json(args.file.read_bytes()).model_dump(
                    mode="json", exclude_unset=True
                )
                method, headers = "POST", {"Idempotency-Key": args.key}
            elif args.command in {"list", "batches"}:
                if not 1 <= args.limit <= 200 or args.offset < 0:
                    raise ValueError("limit must be 1..200 and offset nonnegative")
                path = "v1/experiment-batches" if args.command == "batches" else path
                path += f"?limit={args.limit}&offset={args.offset}"
            else:
                path = f"v1/experiments/{args.id}"
                if args.command in {"results", "cancel"}:
                    path += f"/{args.command}"
                if args.command == "cancel":
                    method = "POST"
                if args.command == "retry-score":
                    path, method = f"v1/score-runs/{args.id}/retry", "POST"
                if args.command == "rescore":
                    path, method = f"v1/attempts/{args.id}/rescore", "POST"
                if args.command in {"report", "gate"}:
                    path = f"v1/comparisons/{args.id}" + ("/gate" if args.command == "gate" else "")
                if args.command in {"batch", "cancel-batch", "wait-batch"}:
                    path = f"v1/experiment-batches/{args.id}"
                    if args.command == "cancel-batch":
                        path, method = path + "/cancel", "POST"
            waiting = args.command in {"wait", "wait-batch"}
            if waiting and (args.deadline <= 0 or args.interval <= 0):
                raise ValueError("wait deadline and interval must be positive")
            deadline = time.monotonic() + (args.deadline if waiting else 0)
            while True:
                response = client.request(method, path, json=payload, headers=headers)
                if not response.is_success:
                    try:
                        detail = response.json()
                    except ValueError:
                        detail = {"error": "non_json_response"}
                    # Server error messages are bounded and sanitized; never print request headers.
                    print(
                        json.dumps(
                            {
                                "error": "api_error",
                                "http_status": response.status_code,
                                "response": detail,
                            }
                        ),
                        file=sys.stderr,
                    )
                    raise SystemExit(3)
                result = response.json()
                if not waiting or result.get("status") in {
                    "completed",
                    "completed_with_unresolved",
                }:
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    print(
                        json.dumps(
                            {
                                "status": "inconclusive",
                                "reason": "wait_deadline",
                                "experiment": result,
                            }
                        )
                    )
                    raise SystemExit(2)
                time.sleep(min(args.interval, remaining))
            print(json.dumps(result, ensure_ascii=False))
            if args.command == "gate":
                raise SystemExit(EXIT.get(result.get("status"), 3))
            if waiting and result["status"] == "completed_with_unresolved":
                raise SystemExit(2)
    except (OSError, ValueError, httpx.HTTPError) as error:
        # Validation errors can embed supplied credentials/config values.
        print(
            json.dumps({"error": "configuration_or_service_error", "type": type(error).__name__}),
            file=sys.stderr,
        )
        raise SystemExit(3) from None


if __name__ == "__main__":
    main()
