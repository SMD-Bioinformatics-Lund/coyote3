#!/usr/bin/env python3
"""Add or repair selected bundled data through a running Coyote3 API; never deploy services."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx  # noqa: E402
from coyote3_client import CoyoteClient  # noqa: E402

from api.contracts.deployment_data import (  # noqa: E402
    DeploymentDataModule,
    DeploymentDataRequest,
)
from coyote3.config.constants import AUTH_PROVIDER_LDAP, AUTH_PROVIDER_LOCAL  # noqa: E402


def manage_data(
    *,
    api_url: str,
    modules: list[DeploymentDataModule],
    force: bool = False,
    username: str = "",
    provider: str = AUTH_PROVIDER_LOCAL,
) -> dict[str, str]:
    """Authenticate, complete first-login password setup, and maintain selected bundled modules.

    Args:
        api_url: Running API URL including any proxy prefix; TLS verification remains enabled.
        modules: Explicit identity, application, knowledgebase or demo selections.
        force: Request repair of selected installation-owned records.
        username: Optional login hint; otherwise prompted interactively.
        provider: Explicit local or ldap authentication provider; defaults to local
            for the initial accounts. An email-shaped username does not imply LDAP.

    Returns:
        Per-catalog installation, repair or preservation statuses.

    Raises:
        PermissionError: No terminal is available or login did not issue a session.
        httpx.HTTPError: Login, password change, authorization or installation fails.
        ValueError: Module selection is invalid or password confirmation does not match.
    """
    payload = DeploymentDataRequest(modules=modules, force=force)
    if provider not in {AUTH_PROVIDER_LOCAL, AUTH_PROVIDER_LDAP}:
        raise ValueError("Choose the local or ldap authentication provider.")
    if not sys.stdin.isatty():
        raise PermissionError("Run interactively to sign in to the API.")
    base = api_url.rstrip("/")
    login = username.strip() or input("Administrator username: ").strip()
    password = getpass.getpass("Administrator password: ")
    with CoyoteClient(base, timeout=600.0) as client:
        user = client.login(username=login, password=password, provider=provider)
        try:
            if getattr(user, "must_change_password", False):
                print("Complete the required password change before installing data.")
                new_password = getpass.getpass("New password: ")
                confirmation = getpass.getpass("Confirm new password: ")
                if new_password != confirmation:
                    raise ValueError("New password and confirmation must match.")
                client.api.auth.password.change.post(
                    json={
                        "current_password": password,
                        "new_password": new_password,
                        "confirm_password": confirmation,
                    },
                )
                # Password changes invalidate all previous sessions, including this one.
                client.login(username=login, password=new_password, provider=provider)
            response = client.api.admin.installation.data.post(
                json=payload.model_dump(),
            )
            return response["collections"]
        finally:
            try:
                client.logout()
            except httpx.HTTPError:
                pass


def main() -> int:
    """Require explicit module selection and report the authenticated maintenance result.

    Returns:
        Zero after success, otherwise one for login, validation or API failures.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-url", default=os.getenv("COYOTE3_API_URL"), required=not os.getenv("COYOTE3_API_URL")
    )
    parser.add_argument(
        "--modules",
        nargs="+",
        required=True,
        choices=("identity", "application", "knowledgebase", "demo"),
    )
    parser.add_argument("--force", action="store_true", help="Repair selected bundled modules")
    parser.add_argument("--username", default="", help="Optional API login username")
    parser.add_argument(
        "--provider", choices=(AUTH_PROVIDER_LOCAL, AUTH_PROVIDER_LDAP), default=AUTH_PROVIDER_LOCAL
    )
    args = parser.parse_args()
    try:
        results = manage_data(
            api_url=args.api_url,
            modules=args.modules,
            force=args.force,
            username=args.username,
            provider=args.provider,
        )
    except (httpx.HTTPError, PermissionError, ValueError, EOFError, KeyboardInterrupt) as error:
        if isinstance(error, httpx.HTTPStatusError):
            message = f"API rejected the operation (HTTP {error.response.status_code})."
        elif isinstance(error, (PermissionError, ValueError)):
            message = str(error)
        else:
            message = "API login or data maintenance failed."
        print(message, file=sys.stderr)
        return 1
    for name, status in results.items():
        print(f"[{status}] {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
