"""Shared transport validation independent of synchronous or asynchronous execution."""

from uuid import UUID

import httpx


def request_headers(token: str, edit_session: str | UUID | None = None) -> dict[str, str]:
    """Keep authentication client-owned while forwarding an optional document lease.

    Args:
        token: Verified API session token held by the client.
        edit_session: Per-editor UUID acquired through the editing API, or None.

    Returns:
        Authentication and, when supplied, the validated editing-session header.

    Raises:
        ValueError: The supplied editing-session value is not a UUID.
    """
    headers = {"Authorization": f"Bearer {token}"}
    if edit_session is not None:
        headers["X-Edit-Session"] = str(UUID(str(edit_session)))
    return headers


def validate_base_url(base_url: str) -> None:
    """Reject URLs that could misdirect authentication or discard a deployment prefix.

    Args:
        base_url: HTTP(S) origin with an optional path prefix, without credentials.

    Raises:
        ValueError: The URL lacks a host or includes credentials, query or fragment.
    """
    url = httpx.URL(base_url)
    if (
        url.scheme not in {"http", "https"}
        or not url.host
        or url.userinfo
        or url.query
        or url.fragment
    ):
        raise ValueError("base_url must be an HTTP(S) origin with an optional mount prefix")
