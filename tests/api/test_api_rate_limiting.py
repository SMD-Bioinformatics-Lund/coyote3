"""API middleware rate-limit behavior tests."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.responses import JSONResponse
from starlette.requests import Request

from api.app import middleware
from api.security.access import ApiUser


@pytest.fixture(autouse=True)
def _enabled_application_modules(monkeypatch: pytest.MonkeyPatch):
    """Keep module-governed routes enabled unless a test overrides the service."""
    from api.app.deps import services as service_dependencies

    class _Controls:
        @staticmethod
        def module_enabled(_module_key: str) -> bool:
            return True

    monkeypatch.setattr(service_dependencies, "get_app_controls_service", lambda: _Controls())


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
        asp_ids=["DNA"],
        asp_groups=[],
        envs=["production"],
        asp_map={},
        auth_type=["local"],
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


@pytest.mark.asyncio
async def test_disabled_application_module_returns_structured_503_before_route_handler(
    monkeypatch: pytest.MonkeyPatch,
):
    """A disabled module must be enforced independently of frontend navigation."""
    from api.app.deps import services as service_dependencies

    class _Controls:
        @staticmethod
        def module_enabled(module_key: str) -> bool:
            return module_key != "reports"

    monkeypatch.setattr(middleware, "ensure_runtime_initialized", lambda **_: None)
    monkeypatch.setattr(middleware, "resolve_request_user", lambda _request: _user())
    monkeypatch.setattr(middleware, "emit_request_event", lambda **_: None)
    monkeypatch.setattr(service_dependencies, "get_app_controls_service", lambda: _Controls())
    middleware.runtime_app.config["API_RATE_LIMIT_ENABLED"] = False
    middleware._API_LIMITER = None
    middleware._API_LIMITER_CFG = None
    route_called = False

    auth_mw = middleware.build_authentication_middleware(testing=True, development=False)

    async def _call_next(_request: Request) -> JSONResponse:
        nonlocal route_called
        route_called = True
        return JSONResponse(status_code=200, content={"status": "ok"})

    response = await auth_mw(
        _request(path="/api/v1/samples/CASE_001/reports/dna/preview"),
        _call_next,
    )
    payload = json.loads(response.body)

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "60"
    assert payload["category"] == "module_disabled"
    assert payload["module"] == "reports"
    assert "temporarily unavailable" in payload["error"]
    assert route_called is False
