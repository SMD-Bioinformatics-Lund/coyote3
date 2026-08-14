"""Browser-facing HTTP security behavior tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from starlette.requests import Request
from starlette.responses import Response

from api.app.middleware import build_security_headers_middleware
from api.security import access


def _request(*, method: str = "GET", headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "scheme": "https",
            "path": "/api/v1/samples",
            "raw_path": b"/api/v1/samples",
            "query_string": b"",
            "headers": headers or [],
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 443),
        }
    )


@pytest.mark.asyncio
async def test_security_headers_cover_browser_and_swagger_assets():
    middleware = build_security_headers_middleware()

    async def downstream(_request: Request) -> Response:
        return Response()

    response = await middleware(_request(), downstream)
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Strict-Transport-Security"].startswith("max-age=")
    assert "cdn.jsdelivr.net" in response.headers["Content-Security-Policy"]


def test_csrf_accepts_bearer_and_matches_cookie_session(monkeypatch: pytest.MonkeyPatch):
    assert access.validate_request_csrf(
        _request(method="PATCH", headers=[(b"authorization", b"Bearer token")])
    )

    repository = SimpleNamespace(
        get=lambda token: SimpleNamespace(csrf_token="csrf") if token == "session" else None
    )
    monkeypatch.setattr(access, "get_api_session_repository", lambda: repository)
    monkeypatch.setattr(access, "get_api_session_cookie_name", lambda: "session_cookie")
    request = _request(
        method="PATCH",
        headers=[(b"cookie", b"session_cookie=session"), (b"x-csrf-token", b"csrf")],
    )
    assert access.validate_request_csrf(request) is True


def test_request_session_is_loaded_once_for_auth_csrf_and_endpoint(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[str] = []
    session = SimpleNamespace(csrf_token="csrf", user=SimpleNamespace(username="reviewer"))
    repository = SimpleNamespace(get=lambda token: calls.append(token) or session)
    monkeypatch.setattr(access, "get_api_session_repository", lambda: repository)
    monkeypatch.setattr(access, "get_api_session_cookie_name", lambda: "session_cookie")
    request = _request(
        method="PATCH",
        headers=[(b"cookie", b"session_cookie=session"), (b"x-csrf-token", b"csrf")],
    )

    assert access.resolve_request_user(request).username == "reviewer"
    assert access.validate_request_csrf(request) is True
    assert access.get_request_api_session(request) is session
    assert calls == ["session"]


def test_csrf_rejects_missing_or_mismatched_cookie_token(monkeypatch: pytest.MonkeyPatch):
    repository = SimpleNamespace(get=lambda _token: SimpleNamespace(csrf_token="expected"))
    monkeypatch.setattr(access, "get_api_session_repository", lambda: repository)
    monkeypatch.setattr(access, "get_api_session_cookie_name", lambda: "session_cookie")
    assert access.validate_request_csrf(_request(method="DELETE")) is False
    request = _request(
        method="DELETE",
        headers=[(b"cookie", b"session_cookie=session"), (b"x-csrf-token", b"wrong")],
    )
    assert access.validate_request_csrf(request) is False


def test_csrf_requirement_is_method_specific_for_public_auth_routes():
    assert access.requires_csrf_validation("POST", "/api/v1/auth/sessions") is False
    assert access.requires_csrf_validation("GET", "/api/v1/auth/sessions/current") is False
    assert access.requires_csrf_validation("DELETE", "/api/v1/auth/sessions/current") is True
