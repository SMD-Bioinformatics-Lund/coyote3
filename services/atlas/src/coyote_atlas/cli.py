# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Inspect references offline or explicitly install a reviewed bundle through the API."""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
from pathlib import Path

import httpx

from coyote_atlas.bundle import ReferenceBundle


def _install(args: argparse.Namespace, plan: dict) -> dict:
    """Apply a pinned bundle through the configured API's authenticated installation route.

    Args:
        args: Explicit URL, token-variable selection and optional trusted CA bundle.
        plan: Locally validated bundle plan whose manifest hash must match the server.

    Returns:
        The server's installation and retained reference metadata result.

    Raises:
        ValueError: URL, token or the reviewed digest is missing or invalid.
        OSError: A selected CA bundle cannot be read.
        httpx.HTTPError: Authentication, authorization, transport or installation fails.
    """
    base_url = args.api_url if args.api_url is not None else os.getenv("COYOTE_ATLAS_API_URL", "")
    try:
        if not base_url or any(char.isspace() or ord(char) < 32 for char in base_url):
            raise ValueError
        url = httpx.URL(base_url)
        if (
            url.scheme not in {"http", "https"}
            or not url.host
            or url.userinfo
            or url.query
            or url.fragment
        ):
            raise ValueError
    except (ValueError, httpx.InvalidURL):
        raise ValueError("Supply a valid API URL without credentials, query or fragment") from None
    if args.expected_manifest_sha256 != plan["manifest_sha256"]:
        raise ValueError("The reviewed manifest hash does not match the local bundle")
    token = os.getenv(args.token_env, "").strip()
    if (
        not token
        or len(token) > 16384
        or not token.isascii()
        or any(ord(c) < 32 or ord(c) == 127 for c in token)
    ):
        raise ValueError("Supply a valid administrator session token through the selected variable")
    ca_bundle = (
        args.ca_bundle if args.ca_bundle is not None else os.getenv("COYOTE_ATLAS_CA_BUNDLE")
    )
    transport = (
        httpx.HTTPTransport(verify=ssl.create_default_context(cafile=ca_bundle))
        if ca_bundle
        else None
    )
    with httpx.Client(
        base_url=base_url.rstrip("/") + "/api/v1/",
        timeout=600.0,
        transport=transport,
        headers={"Authorization": f"Bearer {token}"},
        follow_redirects=False,
    ) as client:
        client.get("auth/session").raise_for_status()
        response = client.post(
            "admin/references/apply",
            json={"expected_manifest_sha256": args.expected_manifest_sha256, "force": args.force},
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("The API installation response must be an object")
        return result


def main(argv: list[str] | None = None) -> int:
    """Run offline bundle commands or an explicitly selected authenticated installation.

    Args:
        argv: CLI arguments without the executable, or None to use process arguments.

    Returns:
        Zero after success, one after validation or API failure; parser errors exit with two.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundle", type=Path, help="Explicit local bundle; default is packaged data"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "validate", "plan"):
        commands.add_parser(name)
    install = commands.add_parser("install", help="Apply a reviewed bundle through the API")
    install.add_argument("--expected-manifest-sha256", required=True)
    install.add_argument("--api-url")
    install.add_argument("--token-env", default="COYOTE_ATLAS_TOKEN")
    install.add_argument("--ca-bundle")
    install.add_argument(
        "--force", action="store_true", help="Request existing bundled repair semantics"
    )
    args = parser.parse_args(argv)
    bundle = ReferenceBundle(args.bundle) if args.bundle is not None else ReferenceBundle.packaged()
    try:
        result = bundle.inspect() if args.command == "inspect" else bundle.plan()
        output = result.model_dump(mode="json")
        if args.command == "install":
            output = _install(args, output)
    except (OSError, ValueError, httpx.HTTPError):
        # Avoid reflecting credentials, raw record contents or host filesystem details.
        print(
            "Reference operation failed; check the bundle, configuration and API authorization.",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
