#!/usr/bin/env python3
"""CLI login helper for Coyote3 API."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure repo root is importable when running as `python scripts/...`.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Authenticate against Coyote3 API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8001", help="API base URL")
    parser.add_argument(
        "--mode",
        choices=("password", "token"),
        required=True,
        help="Authentication mode",
    )
    parser.add_argument("--username", help="Username or email for password mode")
    parser.add_argument("--password", help="Password for password mode")
    parser.add_argument("--token", help="Existing bearer/session token for token mode")
    parser.add_argument(
        "--print-token",
        action="store_true",
        help="Print the resolved session token in output",
    )
    return parser


def main(argv: list[str]) -> int:
    from api.client.auth import login_with_password, login_with_token

    args = build_parser().parse_args(argv)
    if args.mode == "password":
        if not args.username or not args.password:
            raise SystemExit("--username and --password are required in password mode")
        session = login_with_password(
            base_url=args.base_url,
            username=args.username,
            password=args.password,
        )
    else:
        if not args.token:
            raise SystemExit("--token is required in token mode")
        session = login_with_token(base_url=args.base_url, token=args.token)

    payload: dict[str, object] = {
        "status": "ok",
        "base_url": session.base_url,
        "user": session.user,
    }
    if args.print_token:
        payload["session_token"] = session.session_token
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
