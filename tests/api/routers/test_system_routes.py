"""Behavior tests for system/auth API routes."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from api.interfaces.http.operations import auth as auth_router
from api.interfaces.http.operations import health as health_router
from tests.fixtures.api import mock_collections as fx


def _http_request(*, scheme: str = "http", forwarded_scheme: str | None = None) -> Request:
    """Build a minimal browser request for direct authentication-route tests."""
    headers = [] if not forwarded_scheme else [(b"x-forwarded-proto", forwarded_scheme.encode())]
    return Request(
        {
            "type": "http",
            "scheme": scheme,
            "headers": headers,
            "server": ("testserver", 443 if scheme == "https" else 80),
            "path": "/api/v1/auth/sessions",
            "raw_path": b"/api/v1/auth/sessions",
            "query_string": b"",
        }
    )


def _cookie_request(cookie: str) -> Request:
    """Build a minimal authenticated browser request."""
    return Request(
        {
            "type": "http",
            "scheme": "https",
            "headers": [(b"cookie", cookie.encode())],
            "server": ("testserver", 443),
            "path": "/api/v1/auth/session",
            "raw_path": b"/api/v1/auth/session",
            "query_string": b"",
        }
    )


def test_health_returns_ok():
    """Test health returns ok.

    Returns:
        The function result.
    """
    assert health_router.health() == {"status": "ok"}


def test_auth_providers_returns_deployment_configured_providers(monkeypatch):
    """Provider discovery follows deployment configuration, not LDAP connection state."""
    monkeypatch.setattr(auth_router, "AUTH_TYPE_OPTIONS", ("local", "ldap"))
    monkeypatch.setattr(auth_router.ldap_manager, "_server", None)

    assert auth_router.auth_providers_read() == {"providers": ["local", "ldap"]}


def test_auth_login_reports_unconfigured_enabled_ldap(monkeypatch):
    """An enabled LDAP provider fails at login rather than application startup."""
    monkeypatch.setattr(auth_router, "AUTH_TYPE_OPTIONS", ("local", "ldap"))
    monkeypatch.setattr(auth_router.ldap_manager, "_server", None)

    with pytest.raises(HTTPException) as exc:
        auth_router.create_auth_session(
            auth_router.ApiAuthLoginRequest(
                username="user@example.org", password="secret", provider="ldap"
            ),
            _http_request(),
        )

    assert exc.value.status_code == 503
    assert (
        exc.value.detail["error"]
        == "LDAP login is enabled but directory configuration is unavailable"
    )


def test_whoami_sorts_permission_list(monkeypatch):
    """Test whoami sorts permission lists.

    Returns:
        The function result.
    """
    user = fx.api_user()
    user.permissions = ["b", "a"]

    monkeypatch.setattr(
        auth_router,
        "get_request_api_session",
        lambda _request: SimpleNamespace(csrf_token="csrf-test-token"),
    )
    payload = auth_router.whoami(request=SimpleNamespace(), user=user)

    assert payload["permissions"] == ["a", "b"]
    assert payload["ui_settings"] == {
        "analysis_layout": "classic",
        "sample_list_layout": "classic",
        "analysis_modern_view_tried": False,
        "sample_list_modern_view_tried": False,
    }
    assert payload["csrf_token"] == "csrf-test-token"
    assert "denied_permissions" not in payload


def test_current_user_can_update_analysis_layout():
    """The self-service settings route delegates a validated global layout value."""
    user = fx.api_user()
    service = SimpleNamespace(
        update_own_ui_settings=lambda **kwargs: {
            "status": "ok",
            "ui_settings": {"analysis_layout": kwargs["payload"]["analysis_layout"]},
        }
    )

    payload = auth_router.update_current_ui_settings(
        auth_router.ApiUiSettingsUpdateRequest(analysis_layout="modern"),
        user=user,
        service=service,
    )

    assert payload == {"status": "ok", "ui_settings": {"analysis_layout": "modern"}}


def test_auth_login_rejects_invalid_credentials(monkeypatch):
    """Test auth login rejects invalid credentials.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setattr(auth_router, "authenticate_credentials", lambda _u, _p, **_kwargs: None)

    with pytest.raises(HTTPException) as exc:
        auth_router.create_auth_session(
            auth_router.ApiAuthLoginRequest(username="u", password="p", provider="local"),
            _http_request(),
        )

    assert exc.value.status_code == 401
    assert exc.value.detail["error"] == "Invalid credentials"


def test_auth_login_sets_cookie_and_returns_session_payload(monkeypatch):
    """Test auth login sets cookie and returns session payload.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    user_doc = fx.user_doc()
    calls = {}

    monkeypatch.setattr(auth_router, "authenticate_credentials", lambda _u, _p, **_kwargs: user_doc)
    monkeypatch.setattr(
        auth_router,
        "update_user_last_login",
        lambda user_id: calls.setdefault("updated_user", user_id),
    )
    monkeypatch.setattr(
        auth_router,
        "create_api_session",
        lambda user_id, **_kwargs: SimpleNamespace(
            token=f"session-{user_id}", csrf_token="csrf-token"
        ),
    )
    monkeypatch.setattr(
        auth_router, "build_user_session_payload", lambda _doc: {"username": "tester"}
    )
    monkeypatch.setattr(
        auth_router.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )
    monkeypatch.setattr(auth_router, "get_api_session_cookie_name", lambda: "api_session")
    monkeypatch.setattr(auth_router, "get_api_session_cookie_secure", lambda **_kwargs: True)
    monkeypatch.setattr(auth_router, "get_api_session_ttl_seconds", lambda: 600)

    response = auth_router.create_auth_session(
        auth_router.ApiAuthLoginRequest(username=" tester ", password="p", provider="local"),
        _http_request(scheme="https"),
    )

    assert response.status_code == 201
    assert calls["updated_user"] == str(user_doc["username"])
    assert b'"username":"tester"' in response.body
    assert b"session_token" not in response.body
    cookies = response.headers.get("set-cookie", "")
    assert "api_session=session-" in cookies
    assert "HttpOnly" in cookies


def test_create_auth_session_returns_201(monkeypatch):
    """Test create auth session returns 201.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    user_doc = fx.user_doc()

    monkeypatch.setattr(auth_router, "authenticate_credentials", lambda _u, _p, **_kwargs: user_doc)
    monkeypatch.setattr(auth_router, "update_user_last_login", lambda user_id: None)
    monkeypatch.setattr(
        auth_router,
        "create_api_session",
        lambda user_id, **_kwargs: SimpleNamespace(
            token=f"session-{user_id}", csrf_token="csrf-token"
        ),
    )
    monkeypatch.setattr(
        auth_router, "build_user_session_payload", lambda _doc: {"username": "tester"}
    )
    monkeypatch.setattr(
        auth_router.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )
    monkeypatch.setattr(auth_router, "get_api_session_cookie_name", lambda: "api_session")
    monkeypatch.setattr(auth_router, "get_api_session_cookie_secure", lambda **_kwargs: True)
    monkeypatch.setattr(auth_router, "get_api_session_ttl_seconds", lambda: 600)

    response = auth_router.create_auth_session(
        auth_router.ApiAuthLoginRequest(username=" tester ", password="p", provider="local"),
        _http_request(scheme="https"),
    )

    assert response.status_code == 201


def test_auth_login_prefers_business_user_id_for_session(monkeypatch):
    """Test auth login prefers business user id for session.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    user_doc = fx.user_doc()
    user_doc["user_id"] = "coyote3.admin"
    calls = {}

    monkeypatch.setattr(auth_router, "authenticate_credentials", lambda _u, _p, **_kwargs: user_doc)
    monkeypatch.setattr(
        auth_router,
        "update_user_last_login",
        lambda user_id: calls.setdefault("updated_user", user_id),
    )
    monkeypatch.setattr(
        auth_router,
        "create_api_session",
        lambda user_id, **_kwargs: SimpleNamespace(
            token=f"session-{user_id}", csrf_token="csrf-token"
        ),
    )
    monkeypatch.setattr(
        auth_router, "build_user_session_payload", lambda _doc: {"username": "tester"}
    )
    monkeypatch.setattr(
        auth_router.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )
    monkeypatch.setattr(auth_router, "get_api_session_cookie_name", lambda: "api_session")
    monkeypatch.setattr(auth_router, "get_api_session_cookie_secure", lambda **_kwargs: True)
    monkeypatch.setattr(auth_router, "get_api_session_ttl_seconds", lambda: 600)

    response = auth_router.create_auth_session(
        auth_router.ApiAuthLoginRequest(username="tester", password="p", provider="local"),
        _http_request(scheme="https"),
    )

    assert response.status_code == 201
    assert calls["updated_user"] == str(user_doc["username"])
    assert b'"username":"tester"' in response.body
    assert f"session-{user_doc['username']}" in response.headers.get("set-cookie", "")


def test_delete_auth_session_deletes_session_cookie(monkeypatch):
    """Test delete auth session deletes session cookie.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setattr(auth_router, "get_api_session_cookie_name", lambda: "api_session")

    response = auth_router.delete_auth_session()

    assert response.status_code == 200
    assert "api_session=" in response.headers.get("set-cookie", "")


def test_auth_session_serializes_user(monkeypatch):
    """Test auth session serializes user.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setattr(auth_router, "serialize_api_user", lambda user: {"username": user.username})
    monkeypatch.setattr(
        auth_router.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )

    monkeypatch.setattr(
        auth_router,
        "get_request_api_session",
        lambda _request: SimpleNamespace(csrf_token="csrf-token"),
    )
    payload = auth_router.auth_session(
        request=_cookie_request("api_session=session-token"), user=fx.api_user()
    )

    assert payload["status"] == "ok"
    assert payload["user"]["username"] == "tester"
    assert payload["csrf_token"] == "csrf-token"


def test_change_password_rejects_weak_password():
    """Weak new password should fail validation."""
    user = fx.api_user()
    with pytest.raises(HTTPException) as exc:
        auth_router.change_password(
            auth_router.ApiPasswordChangeRequest(
                current_password="old",
                new_password="weak",
            ),
            user=user,
        )
    assert exc.value.status_code == 400


def test_change_password_calls_local_change_flow(monkeypatch):
    """Route delegates to password flow helper."""
    user = fx.api_user()
    calls = {}

    def _change_local_password(**kwargs):
        calls["kwargs"] = kwargs
        return {"status": "ok"}

    monkeypatch.setattr(auth_router, "change_local_password", _change_local_password)
    payload = auth_router.change_password(
        auth_router.ApiPasswordChangeRequest(
            current_password="OldGood!123",
            new_password="NewGood!123",
        ),
        user=user,
    )
    assert payload["status"] == "ok"
    assert calls["kwargs"]["user_id"] == user.username


def test_password_reset_request_always_ok(monkeypatch):
    """Request endpoint should always return ok."""
    calls = {}

    def _issue_password_token_for_user(**kwargs):
        calls["kwargs"] = kwargs
        return {"status": "ok"}

    monkeypatch.setattr(
        auth_router, "issue_password_token_for_user", _issue_password_token_for_user
    )
    payload = auth_router.request_password_reset(
        auth_router.ApiPasswordResetRequest(username="tester")
    )
    assert payload["status"] == "ok"
    assert calls["kwargs"]["purpose"] == "reset"


def test_password_reset_confirm_raises_on_invalid_token(monkeypatch):
    """Confirm endpoint maps flow errors to HTTP 400."""
    monkeypatch.setattr(
        auth_router,
        "consume_password_token_and_set_password",
        lambda **_: {"status": "error", "error": "bad token"},
    )
    with pytest.raises(HTTPException) as exc:
        auth_router.confirm_password_reset(
            auth_router.ApiPasswordResetConfirmRequest(
                token="bad",
                new_password="NewGood!123",
            )
        )
    assert exc.value.status_code == 400


def test_http_exception_handler_preserves_dict_detail():
    """Test http exception handler preserves dict detail.

    Returns:
        The function result.
    """
    exc = HTTPException(status_code=418, detail={"status": 418, "error": "teapot"})

    response = asyncio.run(auth_router.http_exception_handler(None, exc))

    assert response.status_code == 418
    assert b"teapot" in response.body


def test_http_exception_handler_wraps_string_detail():
    """Test http exception handler wraps string detail.

    Returns:
        The function result.
    """
    exc = HTTPException(status_code=400, detail="bad request")

    response = asyncio.run(auth_router.http_exception_handler(None, exc))

    assert response.status_code == 400
    assert b"bad request" in response.body
