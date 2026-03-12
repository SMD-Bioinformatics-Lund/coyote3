"""Server-side API client facade used by Flask web routes."""

from __future__ import annotations

from typing import Any

import httpx
from flask import current_app, g, has_request_context, request

from coyote.services.api_client.base import ApiPayload, ApiRequestError, BaseApiClient


class CoyoteApiClient(BaseApiClient):
    """Thin Flask facade over the shared HTTP transport."""

    pass


def get_web_api_client() -> CoyoteApiClient:
    base_url = current_app.config.get("API_BASE_URL", "http://127.0.0.1:8001")
    timeout_seconds = float(current_app.config.get("API_CLIENT_TIMEOUT_SECONDS", 30.0))
    if has_request_context():
        client = getattr(g, "_coyote_api_client", None)
        if client is None or getattr(client, "_base_url", None) != str(base_url).rstrip("/"):
            transport = httpx.Client(
                timeout=timeout_seconds,
                headers={"Accept": "application/json"},
            )
            client = CoyoteApiClient(base_url=base_url, timeout_seconds=timeout_seconds, client=transport)
            g._coyote_api_client = client
        return client
    return CoyoteApiClient(base_url=base_url, timeout_seconds=timeout_seconds)


def close_web_api_client() -> None:
    if not has_request_context():
        return
    client = getattr(g, "_coyote_api_client", None)
    if client is None:
        return
    try:
        client.close()
    finally:
        g.pop("_coyote_api_client", None)


def _api_cookie_name() -> str:
    if has_request_context():
        return str(current_app.config.get("API_SESSION_COOKIE_NAME", "coyote3_api_session"))
    return "coyote3_api_session"


def build_forward_headers(request_headers: Any) -> dict[str, str]:
    cookie_header = request_headers.get("Cookie")
    request_id = request_headers.get("X-Request-ID")
    if not request_id and has_request_context():
        request_id = getattr(g, "request_id", None)
    headers = {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"}
    if cookie_header:
        headers["Cookie"] = cookie_header
    if request_id:
        headers["X-Request-ID"] = str(request_id)
    return headers


def forward_headers() -> dict[str, str]:
    if not has_request_context():
        return {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"}
    headers = build_forward_headers(request.headers)
    session_token = request.cookies.get(_api_cookie_name())
    if session_token:
        headers["Authorization"] = f"Bearer {session_token}"
    return headers


def build_internal_headers() -> dict[str, str]:
    testing = str(current_app.config.get("TESTING", "")).strip().lower() in {"1", "true", "yes", "on"}
    token = current_app.config.get("INTERNAL_API_TOKEN")
    if not token and testing:
        token = current_app.config.get("SECRET_KEY")
    headers = {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"}
    if token:
        headers["X-Coyote-Internal-Token"] = str(token)
    return headers


__all__ = [
    "ApiPayload",
    "ApiRequestError",
    "CoyoteApiClient",
    "build_forward_headers",
    "build_internal_headers",
    "close_web_api_client",
    "forward_headers",
    "get_web_api_client",
]
