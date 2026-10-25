"""Fluent endpoint objects for the complete HTTP API, including uploads and downloads."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import httpx

if TYPE_CHECKING:
    from coyote3_client.resources import CoyoteClient


def path_segment(value: str) -> str:
    """Encode a resource identifier or literal route segment without allowing traversal.

    Args:
        value: Nonempty segment; slashes, dot segments and backslashes are rejected.

    Returns:
        Percent-encoded segment suitable for a relative API URL.

    Raises:
        ValueError: If the value can change URL path structure.
    """
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError("A nonempty single path segment is required")
    return quote(value, safe="")


class ApiEndpoint:
    """Navigate API paths as objects; only explicit HTTP method calls send requests.

    Attribute names map underscores to hyphens. Brackets preserve exact segment
    spelling and encode identifiers, including names colliding with methods.
    The server remains authoritative for supported routes, payloads and permissions.
    """

    def __init__(self, client: CoyoteClient, path: str = "") -> None:
        """Bind an API-relative path without making a request.

        Args:
            client: Owner of the authenticated transport.
            path: Encoded relative path built by the client, without /api/v1.
        """
        self._client = client
        self._path = path

    def __getitem__(self, segment: str) -> ApiEndpoint:
        """Append an exact route segment or identifier.

        Args:
            segment: Unencoded segment, preserving underscores and other literal characters.

        Returns:
            An endpoint object without making a request.

        Raises:
            ValueError: If the segment is empty or contains path separators.
        """
        return ApiEndpoint(
            self._client, "/".join(filter(None, (self._path, path_segment(segment))))
        )

    def __getattr__(self, name: str) -> ApiEndpoint:
        """Append a route segment using Python attribute spelling.

        Args:
            name: Route segment with underscores representing hyphens.

        Returns:
            A child endpoint reference.

        Raises:
            AttributeError: For private or Python protocol attributes.
        """
        if name.startswith("_"):
            raise AttributeError(name)
        return self[name.replace("_", "-")]

    def request(self, method: str, **kwargs: Any) -> Any:
        """Call this endpoint with HTTPX request arguments and content-aware decoding.

        Args:
            method: HTTP method, such as GET or POST.
            **kwargs: HTTPX params, json, data, files or content; authentication
                headers are owned by the client and cannot be overridden.

        Returns:
            JSON values, text for textual media types, bytes for files, or None for empty bodies.

        Raises:
            RuntimeError: If the client is not authenticated.
            httpx.HTTPError: For transport failures or unsuccessful status codes.
        """
        return self._client._request(method, self._path, **kwargs)

    def get(self, **kwargs: Any) -> Any:
        """Read this endpoint; keyword arguments are HTTPX request arguments."""
        return self.request("GET", **kwargs)

    def post(self, **kwargs: Any) -> Any:
        """Create or invoke this endpoint with explicit HTTPX request arguments."""
        return self.request("POST", **kwargs)

    def put(self, **kwargs: Any) -> Any:
        """Replace this endpoint's resource using HTTPX request arguments."""
        return self.request("PUT", **kwargs)

    def patch(self, **kwargs: Any) -> Any:
        """Update this endpoint's resource using HTTPX request arguments."""
        return self.request("PATCH", **kwargs)

    def delete(self, **kwargs: Any) -> Any:
        """Delete or clear this endpoint using explicit HTTPX request arguments."""
        return self.request("DELETE", **kwargs)

    def stream(self, method: str = "GET", **kwargs: Any) -> AbstractContextManager[httpx.Response]:
        """Open an authenticated stream for file downloads or server-sent events.

        Args:
            method: HTTP method, defaulting to GET.
            **kwargs: HTTPX stream arguments, such as params or json.

        Returns:
            Context manager yielding a response with iter_bytes and iter_lines methods.
            The response closes on context exit; server errors are raised on entry.
        """
        return self._client._stream(method, self._path, **kwargs)
