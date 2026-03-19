"""Behavior tests for system/auth API routes."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.routers import auth as auth_router
from api.routers import health as health_router
from tests.fixtures.api import mock_collections as fx


def test_health_returns_ok():
    """Handle test health returns ok.

    Returns:
        The function result.
    """
    assert health_router.health() == {"status": "ok"}


def test_docs_alias_vi_redirects_to_v1_docs():
    """Handle test docs alias vi redirects to v1 docs.

    Returns:
        The function result.
    """
    response = health_router.docs_alias_vi()
    assert response.status_code == 307
    assert response.headers["location"] == "/api/v1/docs"


def test_whoami_sorts_permission_lists():
    """Handle test whoami sorts permission lists.

    Returns:
        The function result.
    """
    user = fx.api_user()
    user.permissions = ["b", "a"]
    user.denied_permissions = ["z", "y"]

    payload = auth_router.whoami(user=user)

    assert payload["permissions"] == ["a", "b"]
    assert payload["denied_permissions"] == ["y", "z"]


def test_auth_login_rejects_invalid_credentials(monkeypatch):
    """Handle test auth login rejects invalid credentials.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setattr(auth_router, "authenticate_credentials", lambda _u, _p: None)

    with pytest.raises(HTTPException) as exc:
        auth_router.create_auth_session(auth_router.ApiAuthLoginRequest(username="u", password="p"))

    assert exc.value.status_code == 401
    assert exc.value.detail["error"] == "Invalid credentials"


def test_auth_login_sets_cookie_and_returns_session_payload(monkeypatch):
    """Handle test auth login sets cookie and returns session payload.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    user_doc = fx.user_doc()
    calls = {}

    monkeypatch.setattr(auth_router, "authenticate_credentials", lambda _u, _p: user_doc)
    monkeypatch.setattr(
        auth_router,
        "update_user_last_login",
        lambda user_id: calls.setdefault("updated_user", user_id),
    )
    monkeypatch.setattr(
        auth_router, "create_api_session_token", lambda user_id: f"session-{user_id}"
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
    monkeypatch.setattr(auth_router, "get_api_session_cookie_secure", lambda: True)
    monkeypatch.setattr(auth_router, "get_api_session_ttl_seconds", lambda: 600)

    response = auth_router.create_auth_session(
        auth_router.ApiAuthLoginRequest(username=" tester ", password="p")
    )

    assert response.status_code == 201
    assert calls["updated_user"] == str(user_doc["username"])
    assert b'"username":"tester"' in response.body
    assert b"session_token" not in response.body
    cookies = response.headers.get("set-cookie", "")
    assert "api_session=session-" in cookies
    assert "HttpOnly" in cookies


def test_create_auth_session_returns_201(monkeypatch):
    """Handle test create auth session returns 201.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    user_doc = fx.user_doc()

    monkeypatch.setattr(auth_router, "authenticate_credentials", lambda _u, _p: user_doc)
    monkeypatch.setattr(auth_router, "update_user_last_login", lambda user_id: None)
    monkeypatch.setattr(
        auth_router, "create_api_session_token", lambda user_id: f"session-{user_id}"
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
    monkeypatch.setattr(auth_router, "get_api_session_cookie_secure", lambda: True)
    monkeypatch.setattr(auth_router, "get_api_session_ttl_seconds", lambda: 600)

    response = auth_router.create_auth_session(
        auth_router.ApiAuthLoginRequest(username=" tester ", password="p")
    )

    assert response.status_code == 201


def test_auth_login_prefers_business_user_id_for_session(monkeypatch):
    """Handle test auth login prefers business user id for session.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    user_doc = fx.user_doc()
    user_doc["user_id"] = "coyote3.admin"
    calls = {}

    monkeypatch.setattr(auth_router, "authenticate_credentials", lambda _u, _p: user_doc)
    monkeypatch.setattr(
        auth_router,
        "update_user_last_login",
        lambda user_id: calls.setdefault("updated_user", user_id),
    )
    monkeypatch.setattr(
        auth_router, "create_api_session_token", lambda user_id: f"session-{user_id}"
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
    monkeypatch.setattr(auth_router, "get_api_session_cookie_secure", lambda: True)
    monkeypatch.setattr(auth_router, "get_api_session_ttl_seconds", lambda: 600)

    response = auth_router.create_auth_session(
        auth_router.ApiAuthLoginRequest(username="tester", password="p")
    )

    assert response.status_code == 201
    assert calls["updated_user"] == str(user_doc["username"])
    assert b'"username":"tester"' in response.body
    assert f"session-{user_doc['username']}" in response.headers.get("set-cookie", "")


def test_delete_auth_session_deletes_session_cookie(monkeypatch):
    """Handle test delete auth session deletes session cookie.

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
    """Handle test auth session serializes user.

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

    payload = auth_router.auth_session(user=fx.api_user())

    assert payload["status"] == "ok"
    assert payload["user"]["username"] == "tester"


def test_http_exception_handler_preserves_dict_detail():
    """Handle test http exception handler preserves dict detail.

    Returns:
        The function result.
    """
    exc = HTTPException(status_code=418, detail={"status": 418, "error": "teapot"})

    response = asyncio.run(auth_router.http_exception_handler(None, exc))

    assert response.status_code == 418
    assert b"teapot" in response.body


def test_http_exception_handler_wraps_string_detail():
    """Handle test http exception handler wraps string detail.

    Returns:
        The function result.
    """
    exc = HTTPException(status_code=400, detail="bad request")

    response = asyncio.run(auth_router.http_exception_handler(None, exc))

    assert response.status_code == 400
    assert b"bad request" in response.body
