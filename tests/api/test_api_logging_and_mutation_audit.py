"""API request-id correlation and mutation-audit tests."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.responses import JSONResponse
from starlette.requests import Request

from api import middleware
from api.security.access import ApiUser


def _user(level: int = 9) -> ApiUser:
    """Build a lightweight authenticated API user."""
    return ApiUser(
        id="U1",
        email="user@example.org",
        fullname="User Example",
        username="user1",
        role="user",
        access_level=level,
        permissions=[],
        denied_permissions=[],
        assays=["DNA", "RNA"],
        assay_groups=[],
        envs=["production"],
        asp_map={},
    )


def _request(*, path: str, method: str, headers: dict[str, str] | None = None) -> Request:
    """Build a minimal Starlette request object."""
    raw_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    scope: dict[str, Any] = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode("latin-1"),
        "query_string": b"",
        "headers": raw_headers,
        "scheme": "http",
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_api_response_includes_request_id_header(monkeypatch: pytest.MonkeyPatch):
    """Middleware should propagate incoming request-id to response headers."""
    monkeypatch.setattr(middleware, "ensure_runtime_initialized", lambda **_: None)
    monkeypatch.setattr(middleware, "resolve_request_user", lambda _request: _user(level=9))

    auth_mw = middleware.build_authentication_middleware(testing=True, development=False)

    async def _call_next(_request: Request) -> JSONResponse:
        return JSONResponse(status_code=200, content={"status": "ok"})

    response = await auth_mw(
        _request(
            path="/api/v1/coverage/blacklist/entries",
            method="POST",
            headers={"X-Request-ID": "rid-123"},
        ),
        _call_next,
    )

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "rid-123"


@pytest.mark.asyncio
async def test_mutation_event_emits_request_id_user_and_target(monkeypatch: pytest.MonkeyPatch):
    """Mutation audit event should include user, action, target, and request-id context."""
    captured: dict[str, Any] = {}

    def _capture_mutation_event(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(middleware, "ensure_runtime_initialized", lambda **_: None)
    monkeypatch.setattr(middleware, "resolve_request_user", lambda _request: _user(level=9))
    monkeypatch.setattr(middleware, "emit_mutation_event", _capture_mutation_event)

    auth_mw = middleware.build_authentication_middleware(testing=True, development=False)

    async def _call_next(_request: Request) -> JSONResponse:
        return JSONResponse(status_code=200, content={"status": "ok"})

    request = _request(
        path="/api/v1/coverage/blacklist/entries",
        method="POST",
        headers={"X-Request-ID": "rid-456"},
    )
    response = await auth_mw(request, _call_next)

    assert response.status_code == 200
    assert captured["username"] == "user1"
    assert captured["action"] == "POST"
    assert captured["target"] == "/api/v1/coverage/blacklist/entries"
    assert captured["request"].headers.get("X-Request-ID") == "rid-456"
