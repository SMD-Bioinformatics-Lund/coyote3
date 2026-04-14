"""API middleware rate-limit behavior tests."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.responses import JSONResponse
from starlette.requests import Request

from api import middleware
from api.security.access import ApiUser


def _user() -> ApiUser:
    """Build a minimal authenticated API user."""
    return ApiUser(
        id="U1",
        email="user@example.org",
        fullname="User Example",
        username="user1",
        role="user",
        roles=["user"],
        access_level=9,
        permissions=[],
        denied_permissions=[],
        assays=["DNA"],
        assay_groups=[],
        envs=["production"],
        asp_map={},
    )


def _request(*, path: str, method: str = "GET", ip: str = "127.0.0.1") -> Request:
    """Build a minimal Starlette request object for middleware testing."""
    scope: dict[str, Any] = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode("latin-1"),
        "query_string": b"",
        "headers": [],
        "scheme": "http",
        "client": (ip, 12345),
        "server": ("testserver", 80),
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_api_rate_limit_returns_429_and_retry_after(monkeypatch: pytest.MonkeyPatch):
    """When the API limit is exceeded the middleware should return a 429 response."""
    monkeypatch.setattr(middleware, "ensure_runtime_initialized", lambda **_: None)
    monkeypatch.setattr(middleware, "resolve_request_user", lambda _request: _user())
    middleware.runtime_app.config.update(
        {
            "API_RATE_LIMIT_ENABLED": True,
            "API_RATE_LIMIT_REQUESTS_PER_MINUTE": 1,
            "API_RATE_LIMIT_WINDOW_SECONDS": 60,
        }
    )
    middleware._API_LIMITER = None
    middleware._API_LIMITER_CFG = None

    auth_mw = middleware.build_authentication_middleware(testing=True, development=False)

    async def _call_next(_request: Request) -> JSONResponse:
        return JSONResponse(status_code=200, content={"status": "ok"})

    first = await auth_mw(_request(path="/api/v1/reports"), _call_next)
    second = await auth_mw(_request(path="/api/v1/reports"), _call_next)

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers.get("Retry-After") is not None
    assert second.headers.get("X-Request-ID")
    assert b"Too many requests" in second.body


@pytest.mark.asyncio
async def test_api_excluded_health_route_is_not_rate_limited(monkeypatch: pytest.MonkeyPatch):
    """Excluded API routes should bypass limiter checks."""
    monkeypatch.setattr(middleware, "ensure_runtime_initialized", lambda **_: None)
    monkeypatch.setattr(middleware, "resolve_request_user", lambda _request: _user())
    middleware.runtime_app.config.update(
        {
            "API_RATE_LIMIT_ENABLED": True,
            "API_RATE_LIMIT_REQUESTS_PER_MINUTE": 1,
            "API_RATE_LIMIT_WINDOW_SECONDS": 60,
        }
    )
    middleware._API_LIMITER = None
    middleware._API_LIMITER_CFG = None

    auth_mw = middleware.build_authentication_middleware(testing=True, development=False)

    async def _call_next(_request: Request) -> JSONResponse:
        return JSONResponse(status_code=200, content={"status": "ok"})

    first = await auth_mw(_request(path="/api/v1/health"), _call_next)
    second = await auth_mw(_request(path="/api/v1/health"), _call_next)

    assert first.status_code == 200
    assert second.status_code == 200


@pytest.mark.asyncio
async def test_successful_health_route_is_suppressed_from_api_access_log(
    monkeypatch: pytest.MonkeyPatch,
):
    """Successful health checks should skip normal API access logging."""
    monkeypatch.setattr(middleware, "ensure_runtime_initialized", lambda **_: None)
    monkeypatch.setattr(middleware, "resolve_request_user", lambda _request: _user())
    monkeypatch.setattr(middleware, "emit_request_event", lambda **_: None)
    logged: list[tuple] = []
    monkeypatch.setattr(
        middleware.runtime_app.logger, "info", lambda *args, **kwargs: logged.append(args)
    )
    monkeypatch.setattr(
        middleware.runtime_app.logger, "warning", lambda *args, **kwargs: logged.append(args)
    )
    monkeypatch.setattr(
        middleware.runtime_app.logger, "error", lambda *args, **kwargs: logged.append(args)
    )

    auth_mw = middleware.build_authentication_middleware(testing=True, development=False)

    async def _call_next(_request: Request) -> JSONResponse:
        return JSONResponse(status_code=200, content={"status": "ok"})

    response = await auth_mw(_request(path="/api/v1/health"), _call_next)

    assert response.status_code == 200
    assert logged == []
