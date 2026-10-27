#!/usr/bin/env python3
"""CLI login helper for Coyote3 API."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure repo root is importable when running as `python scripts/...`.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def build_parser() -> argparse.ArgumentParser:
    """Define password and token authentication options without parsing arguments.

    Returns:
        Parser requiring an authentication mode, with token output disabled by default.
    """
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
    parser.add_argument("--password-env", help="Environment variable containing the password")
    parser.add_argument(
        "--provider",
        choices=("local", "ldap"),
        help="Configured provider for password mode; verify availability with /api/v1/auth/providers",
    )
    parser.add_argument("--token", help="Existing bearer/session token for token mode")
    parser.add_argument(
        "--print-token",
        action="store_true",
        help="Print the resolved session token in output",
    )
    return parser


def main(argv: list[str]) -> int:
    """Authenticate with the API and print session metadata as JSON.

    Args:
        argv: Command-line arguments excluding the executable name.

    Returns:
        Zero after successful authentication and output.

    Raises:
        SystemExit: Arguments are invalid, help is requested, or mode-specific
            credentials are missing.
        httpx.HTTPError: The authentication request fails or returns an error status.

    Notes:
        Password mode creates a session; token mode validates an existing token.
        The session token is printed only with ``--print-token``.
    """
    from coyote3_client import CoyoteClient

    args = build_parser().parse_args(argv)
    if args.password_env:
        if args.password:
            raise SystemExit("Choose --password or --password-env, not both")
        args.password = os.environ.get(args.password_env)
    if args.mode == "password":
        if not args.username or not args.password or not args.provider:
            raise SystemExit("--username, --password, and --provider are required in password mode")
    else:
        if not args.token:
            raise SystemExit("--token is required in token mode")
    with CoyoteClient(args.base_url) as client:
        user = (
            client.login(username=args.username, password=args.password, provider=args.provider)
            if args.mode == "password"
            else client.login_with_token(args.token)
        )
        payload: dict[str, object] = {
            "status": "ok",
            "base_url": args.base_url.rstrip("/"),
            "user": user.model_dump(mode="json"),
        }
        if args.print_token:
            payload["session_token"] = client.session_token
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
