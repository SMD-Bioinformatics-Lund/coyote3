"""Browser-facing HTTP security behavior tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from coyote_api.app import middleware as http_middleware
from coyote_api.app.deps import services
from coyote_api.app.middleware import build_security_headers_middleware
from coyote_api.security import access
from starlette.requests import Request
from starlette.responses import Response


def _request(
    *,
    method: str = "GET",
    path: str = "/api/v1/samples",
    root_path: str = "",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "scheme": "https",
            "path": path,
            "root_path": root_path,
            "raw_path": path.encode(),
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
    assert "script-src 'self' 'unsafe-inline'" not in response.headers["Content-Security-Policy"]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/v1/docs", "/api/v1/redoc"])
@pytest.mark.parametrize(
    "root_path,prefix",
    [("", ""), ("/center", "/center"), ("/center", ""), ("/api/v", "")],
)
async def test_openapi_ui_security_policy_allows_its_inline_bootstrap(
    path: str, root_path: str, prefix: str
):
    middleware = build_security_headers_middleware()

    async def downstream(_request: Request) -> Response:
        return Response()

    response = await middleware(_request(path=f"{prefix}{path}", root_path=root_path), downstream)

    policy = response.headers["Content-Security-Policy"]
    assert "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net" in policy
    assert "font-src 'self' data: https://cdn.jsdelivr.net" in policy
    assert "worker-src 'self' blob:" in policy


@pytest.mark.asyncio
async def test_mounted_api_routes_keep_the_strict_security_policy():
    middleware = build_security_headers_middleware()

    async def downstream(_request: Request) -> Response:
        return Response()

    response = await middleware(
        _request(path="/center/api/v1/samples", root_path="/center"), downstream
    )
    policy = response.headers["Content-Security-Policy"]
    assert "script-src 'self' 'unsafe-inline'" not in policy
    assert "worker-src 'self' blob:" not in policy


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


def test_csrf_rejects_non_ascii_header_without_raising(monkeypatch: pytest.MonkeyPatch):
    """Malformed browser credentials must be rejected rather than produce HTTP 500."""
    repository = SimpleNamespace(get=lambda _token: SimpleNamespace(csrf_token="expected"))
    monkeypatch.setattr(access, "get_api_session_repository", lambda: repository)
    monkeypatch.setattr(access, "get_api_session_cookie_name", lambda: "session_cookie")
    request = _request(
        method="PATCH",
        headers=[(b"cookie", b"session_cookie=session"), (b"x-csrf-token", b"invalid-\xff")],
    )
    assert access.validate_request_csrf(request) is False


@pytest.fixture
def authenticated_boundary(monkeypatch: pytest.MonkeyPatch):
    """Use real session resolution and CSRF checks against one synthetic session."""
    user = SimpleNamespace(username="reviewer")
    session = SimpleNamespace(user=user, csrf_token="expected-csrf")
    repository = SimpleNamespace(get=lambda token: session if token == "session" else None)
    events, mutations = [], []
    monkeypatch.setattr(http_middleware, "ensure_runtime_initialized", lambda **_: None)
    monkeypatch.setattr(http_middleware, "_get_api_limiter", lambda: None)
    monkeypatch.setattr(http_middleware, "emit_request_event", lambda **event: events.append(event))
    monkeypatch.setattr(
        http_middleware, "emit_mutation_event", lambda **event: mutations.append(event)
    )
    monkeypatch.setitem(http_middleware.runtime_app.config, "API_CSRF_ENABLED", True)
    monkeypatch.setattr(access, "get_api_session_repository", lambda: repository)
    monkeypatch.setattr(access, "get_api_session_cookie_name", lambda: "session_cookie")
    monkeypatch.setattr(services, "get_audit_service", lambda: None)
    return SimpleNamespace(
        run=http_middleware.build_authentication_middleware(testing=True, development=False),
        events=events,
        mutations=mutations,
    )


@pytest.fixture(
    params=[("", ""), ("/center", "/center"), ("/center", ""), ("/api/v", "")],
    ids=["root", "mounted", "proxy-stripped", "partial-segment"],
)
def deployment_path(request):
    """Supply equivalent ASGI deployment paths without changing application routes."""
    return request.param


@pytest.mark.asyncio
async def test_deployment_prefix_cannot_bypass_authentication(
    authenticated_boundary, deployment_path
):
    root_path, prefix = deployment_path

    async def protected(_request):
        pytest.fail("Unauthenticated request reached the protected handler")

    response = await authenticated_boundary.run(
        _request(path=f"{prefix}/api/v1/samples", root_path=root_path), protected
    )
    assert response.status_code == 401
    assert response.headers["X-Request-ID"]
    assert authenticated_boundary.events[0]["extra"] == {"kind": "authentication"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "csrf_token,expected_status", [(None, 403), (b"wrong", 403), (b"expected-csrf", 200)]
)
async def test_deployment_prefix_preserves_cookie_csrf_and_mutation_audit(
    authenticated_boundary, deployment_path, csrf_token, expected_status
):
    root_path, prefix = deployment_path
    calls = []

    async def protected(request):
        calls.append(request)
        return Response(status_code=200)

    headers = [(b"cookie", b"session_cookie=session")]
    if csrf_token is not None:
        headers.append((b"x-csrf-token", csrf_token))
    response = await authenticated_boundary.run(
        _request(
            method="POST", path=f"{prefix}/api/v1/samples", root_path=root_path, headers=headers
        ),
        protected,
    )
    assert response.status_code == expected_status
    assert bool(calls) is (expected_status == 200)
    if expected_status == 403:
        assert authenticated_boundary.events[0]["extra"] == {"kind": "csrf_validation_failed"}
        assert authenticated_boundary.mutations == []
    else:
        assert authenticated_boundary.mutations[0]["target"] == "/api/v1/samples"
        assert authenticated_boundary.mutations[0]["username"] == "reviewer"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path", [("GET", "/api/v1/health"), ("POST", "/api/v1/auth/sessions")]
)
async def test_deployment_prefix_preserves_explicit_public_entry_points(
    authenticated_boundary, deployment_path, method, path
):
    root_path, prefix = deployment_path

    async def public(_request):
        return Response(status_code=200)

    response = await authenticated_boundary.run(
        _request(method=method, path=f"{prefix}{path}", root_path=root_path), public
    )
    assert response.status_code == 200
    assert authenticated_boundary.mutations == []
