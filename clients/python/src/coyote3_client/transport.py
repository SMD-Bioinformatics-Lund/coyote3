"""Shared transport validation independent of synchronous or asynchronous execution."""

import httpx


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
