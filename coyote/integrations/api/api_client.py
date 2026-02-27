"""Server-side API client facade used by Flask web routes."""

from __future__ import annotations

from typing import Any

from flask import current_app, has_request_context, request

from coyote.integrations.api.base import ApiRequestError, BaseApiClient


class CoyoteApiClient(BaseApiClient):
    """Thin Flask facade over the shared HTTP transport."""

    pass


def get_web_api_client() -> CoyoteApiClient:
    return CoyoteApiClient(base_url=current_app.config.get("API_BASE_URL", "http://127.0.0.1:8001"))


def build_forward_headers(request_headers: Any) -> dict[str, str]:
    cookie_header = request_headers.get("Cookie")
    headers = {"X-Requested-With": "XMLHttpRequest"}
    if cookie_header:
        headers["Cookie"] = cookie_header
    return headers


def forward_headers() -> dict[str, str]:
    if not has_request_context():
        return {"X-Requested-With": "XMLHttpRequest"}
    return build_forward_headers(request.headers)


def build_internal_headers() -> dict[str, str]:
    token = current_app.config.get("INTERNAL_API_TOKEN") or current_app.config.get("SECRET_KEY")
    headers = {"X-Requested-With": "XMLHttpRequest"}
    if token:
        headers["X-Coyote-Internal-Token"] = str(token)
    return headers
