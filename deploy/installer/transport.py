# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Narrow HTTP session helpers for application administration commands."""

from typing import Any

import httpx
from coyote_api.config.factory_defaults import api_default


def api_client(
    base_url: str, *, timeout: float = 30.0, transport: httpx.BaseTransport | None = None
) -> httpx.Client:
    """Create a TLS-verified transport preserving an optional deployment prefix.

    Args:
        base_url: HTTP(S) application origin and optional mount prefix.
        timeout: Request timeout in seconds.
        transport: Explicit transport for synthetic tests, or the normal HTTP transport.

    Returns:
        Unauthenticated client to close with a context manager.

    Raises:
        ValueError: The URL contains credentials, query, fragment or invalid characters.
    """
    try:
        url = httpx.URL(base_url)
        if (
            not base_url
            or any(character.isspace() or ord(character) < 32 for character in base_url)
            or url.scheme not in {"http", "https"}
            or not url.host
            or url.userinfo
            or url.query
            or url.fragment
        ):
            raise ValueError
    except (ValueError, httpx.InvalidURL):
        raise ValueError(
            "Supply an HTTP(S) API URL without credentials, query or fragment"
        ) from None
    return httpx.Client(
        base_url=base_url.rstrip("/") + "/api/v1/",
        timeout=timeout,
        transport=transport,
        follow_redirects=False,
    )


def response_object(response: httpx.Response) -> dict[str, Any]:
    """Reject HTTP errors and non-object responses without reflecting response bodies."""
    response.raise_for_status()
    try:
        result = response.json()
    except ValueError:
        raise ValueError("The API returned an invalid JSON response") from None
    if not isinstance(result, dict):
        raise ValueError("The API response must be an object")
    return result


def authenticate(
    client: httpx.Client, *, username: str, password: str, provider: str
) -> dict[str, Any]:
    """Create a session and use only the configured session cookie as its bearer token.

    Args:
        client: Application administration transport.
        username: Explicit account identity.
        password: Current password, retained only for this request.
        provider: Explicit configured authentication provider.

    Returns:
        Authenticated user fields from the session response.

    Raises:
        httpx.HTTPError: Authentication fails.
        ValueError: The response lacks its user or configured session cookie.
    """
    client.headers.pop("Authorization", None)
    client.cookies.clear()
    try:
        response = client.post(
            "auth/sessions", json={"username": username, "password": password, "provider": provider}
        )
        payload = response_object(response)
        user = payload.get("user")
        token = response.cookies.get(api_default("runtime.API_SESSION_COOKIE_NAME", str))
        if not isinstance(user, dict) or not token:
            raise ValueError("API login did not return a user and session cookie")
        client.headers["Authorization"] = f"Bearer {token}"
        return user
    finally:
        # Mutations use the bearer header, never incidental authentication cookies.
        client.cookies.clear()


def logout(client: httpx.Client) -> None:
    """Revoke the command's session and discard local authentication on any outcome."""
    try:
        if "Authorization" in client.headers:
            client.delete("auth/sessions/current").raise_for_status()
    finally:
        client.headers.pop("Authorization", None)
        client.cookies.clear()
