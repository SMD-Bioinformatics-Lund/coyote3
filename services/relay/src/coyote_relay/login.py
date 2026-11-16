#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""CLI login helper for Coyote4 API."""

from __future__ import annotations

import argparse
import json
import os
import ssl

import httpx

from coyote_relay.config import ApiConnection, configured_value, read_token


def build_parser() -> argparse.ArgumentParser:
    """Define password and token authentication options without parsing arguments.

    Returns:
        Parser requiring an authentication mode, with token output disabled by default.
    """
    parser = argparse.ArgumentParser(description="Authenticate against Coyote4 API.")
    parser.add_argument("--base-url", help="API URL, or COYOTE_RELAY_API_URL")
    parser.add_argument("--ca-bundle", help="Trusted CA bundle, or COYOTE_RELAY_CA_BUNDLE")
    parser.add_argument(
        "--mode",
        choices=("password", "token"),
        required=True,
        help="Authentication mode",
    )
    parser.add_argument("--username", help="Username or email, or COYOTE_RELAY_USERNAME")
    password_source = parser.add_mutually_exclusive_group()
    password_source.add_argument("--password", help="Password, or COYOTE_RELAY_PASSWORD")
    password_source.add_argument(
        "--password-env", help="Environment variable containing the password"
    )
    parser.add_argument(
        "--provider",
        choices=("local", "ldap"),
        help="Configured provider, or COYOTE_RELAY_PROVIDER; verify with /api/v1/auth/providers",
    )
    token_source = parser.add_mutually_exclusive_group()
    token_source.add_argument(
        "--token", help="Existing bearer/session token, or COYOTE_RELAY_TOKEN"
    )
    token_source.add_argument("--token-file", help="Read a bearer/session token from a local file")
    token_source.add_argument(
        "--token-env", help="Read a bearer/session token from this environment variable"
    )
    parser.add_argument(
        "--print-token",
        action="store_true",
        help="Print the resolved session token in output",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Authenticate with the API and print session metadata as JSON.

    Args:
        argv: Arguments excluding the executable name; None reads process arguments.

    Returns:
        Zero after successful authentication and output.

    Raises:
        SystemExit: Arguments are invalid, help is requested, or mode-specific
            credentials are missing.
        httpx.HTTPError: The authentication request fails or returns an error status.
        OSError: The selected trusted CA bundle cannot be loaded.

    Notes:
        Password mode creates a session; token mode validates an existing token.
        The session token is printed only with ``--print-token``. Explicit connection
        and credential options override Relay environment variables. HTTPS certificate
        verification remains enabled when a custom CA bundle is selected.
    """
    from coyote_pyclient import CoyoteClient

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        connection = ApiConnection.resolve(base_url=args.base_url, ca_bundle=args.ca_bundle)
    except ValueError as exc:
        parser.error(str(exc))
    args.username = configured_value("username", args.username)
    args.provider = configured_value("provider", args.provider)
    if args.password_env is not None:
        args.password = os.environ.get(args.password_env)
    else:
        args.password = configured_value("password", args.password)
    if args.mode == "password":
        if not args.username or not args.password or not args.provider:
            parser.error(
                "Password mode requires username, password and provider through CLI or COYOTE_RELAY_* variables"
            )
        if args.provider not in {"local", "ldap"}:
            parser.error("Provider must be local or ldap")
    else:
        try:
            args.token = read_token(
                token=args.token, token_file=args.token_file, token_env=args.token_env
            )
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
    transport = (
        httpx.HTTPTransport(verify=ssl.create_default_context(cafile=connection.ca_bundle))
        if connection.ca_bundle
        else None
    )
    with CoyoteClient(connection.base_url, transport=transport) as client:
        user = (
            client.login(username=args.username, password=args.password, provider=args.provider)
            if args.mode == "password"
            else client.login_with_token(args.token)
        )
        payload: dict[str, object] = {
            "status": "ok",
            "base_url": connection.base_url,
            "user": user.model_dump(mode="json"),
        }
        if args.print_token:
            payload["session_token"] = client.session_token
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
