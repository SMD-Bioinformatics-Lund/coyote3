"""Behavior tests for system/auth API routes."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from api.routes import system
from tests.api.fixtures import mock_collections as fx


def test_health_returns_ok():
    assert system.health() == {"status": "ok"}


def test_docs_alias_vi_redirects_to_v1_docs():
    response = system.docs_alias_vi()
    assert response.status_code == 307
    assert response.headers["location"] == "/api/v1/docs"


def test_whoami_sorts_permission_lists():
    user = fx.api_user()
    user.permissions = ["b", "a"]
    user.denied_permissions = ["z", "y"]

    payload = system.whoami(user=user)

    assert payload["permissions"] == ["a", "b"]
    assert payload["denied_permissions"] == ["y", "z"]


def test_auth_login_rejects_invalid_credentials(monkeypatch):
    monkeypatch.setattr(system, "authenticate_credentials", lambda _u, _p: None)

    with pytest.raises(HTTPException) as exc:
        system.auth_login(system.ApiAuthLoginRequest(username="u", password="p"))

    assert exc.value.status_code == 401
    assert exc.value.detail["error"] == "Invalid credentials"


def test_auth_login_sets_cookie_and_returns_session_payload(monkeypatch):
    user_doc = fx.user_doc()
    calls = {}

    monkeypatch.setattr(system, "authenticate_credentials", lambda _u, _p: user_doc)
    monkeypatch.setattr(
        system,
        "update_user_last_login",
        lambda user_id: calls.setdefault("updated_user", user_id),
    )
    monkeypatch.setattr(system, "create_api_session_token", lambda user_id: f"session-{user_id}")
    monkeypatch.setattr(system, "build_user_session_payload", lambda _doc: {"username": "tester"})
    monkeypatch.setattr(system.util.common, "convert_to_serializable", lambda payload: payload)
    monkeypatch.setattr(system, "get_api_session_cookie_name", lambda: "api_session")
    monkeypatch.setattr(system, "get_api_session_cookie_secure", lambda: True)
    monkeypatch.setattr(system, "get_api_session_ttl_seconds", lambda: 600)

    response = system.auth_login(system.ApiAuthLoginRequest(username=" tester ", password="p"))

    assert response.status_code == 200
    assert calls["updated_user"] == str(user_doc["user_id"])
    assert b"session-" in response.body
    cookies = response.headers.get("set-cookie", "")
    assert "api_session=session-" in cookies
    assert "HttpOnly" in cookies


def test_auth_login_prefers_business_user_id_for_session(monkeypatch):
    user_doc = fx.user_doc()
    user_doc["user_id"] = "coyote3.admin"
    calls = {}

    monkeypatch.setattr(system, "authenticate_credentials", lambda _u, _p: user_doc)
    monkeypatch.setattr(
        system,
        "update_user_last_login",
        lambda user_id: calls.setdefault("updated_user", user_id),
    )
    monkeypatch.setattr(system, "create_api_session_token", lambda user_id: f"session-{user_id}")
    monkeypatch.setattr(system, "build_user_session_payload", lambda _doc: {"username": "tester"})
    monkeypatch.setattr(system.util.common, "convert_to_serializable", lambda payload: payload)
    monkeypatch.setattr(system, "get_api_session_cookie_name", lambda: "api_session")
    monkeypatch.setattr(system, "get_api_session_cookie_secure", lambda: True)
    monkeypatch.setattr(system, "get_api_session_ttl_seconds", lambda: 600)

    response = system.auth_login(system.ApiAuthLoginRequest(username="tester", password="p"))

    assert response.status_code == 200
    assert calls["updated_user"] == "coyote3.admin"
    assert b"session-coyote3.admin" in response.body


def test_auth_logout_deletes_session_cookie(monkeypatch):
    monkeypatch.setattr(system, "get_api_session_cookie_name", lambda: "api_session")

    response = system.auth_logout()

    assert response.status_code == 200
    assert "api_session=" in response.headers.get("set-cookie", "")


def test_auth_me_serializes_user(monkeypatch):
    monkeypatch.setattr(system, "serialize_api_user", lambda user: {"username": user.username})
    monkeypatch.setattr(system.util.common, "convert_to_serializable", lambda payload: payload)

    payload = system.auth_me(user=fx.api_user())

    assert payload["status"] == "ok"
    assert payload["user"]["username"] == "tester"


def test_http_exception_handler_preserves_dict_detail():
    exc = HTTPException(status_code=418, detail={"status": 418, "error": "teapot"})

    response = asyncio.run(system.http_exception_handler(None, exc))

    assert response.status_code == 418
    assert b"teapot" in response.body


def test_http_exception_handler_wraps_string_detail():
    exc = HTTPException(status_code=400, detail="bad request")

    response = asyncio.run(system.http_exception_handler(None, exc))

    assert response.status_code == 400
    assert b"bad request" in response.body
