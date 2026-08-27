from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.security import password_flows


class _UserRepository:
    def __init__(self, user: dict | None = None) -> None:
        self.user = user
        self.token_valid = True
        self.issued: dict | None = None
        self.password_update: dict | None = None

    def user_with_id(self, _user_id: str):
        return self.user

    def set_password_action_token(self, **kwargs):
        self.issued = kwargs

    def validate_and_clear_password_action_token(self, **_kwargs):
        return self.token_valid

    def set_local_password(self, **kwargs):
        self.password_update = kwargs


@pytest.fixture
def password_runtime(monkeypatch):
    config = {
        "SECRET_KEY": "test-secret",
        "PASSWORD_TOKEN_SALT": "test-salt",
        "PASSWORD_TOKEN_TTL_SECONDS": 120,
        "PUBLIC_BASE_URL": "https://example.test",
        "SCRIPT_NAME": "/coyote3",
    }
    monkeypatch.setattr(password_flows.runtime_app, "config", config)
    monkeypatch.setattr(
        password_flows.runtime_app,
        "logger",
        SimpleNamespace(exception=lambda *_args, **_kwargs: None),
    )
    monkeypatch.setattr(password_flows, "emit_auth_metric", lambda *_args, **_kwargs: None)
    return config


def test_token_configuration_and_url_helpers(password_runtime, monkeypatch):
    assert password_flows._password_token_ttl_seconds() == 120
    assert password_flows._build_set_password_url("abc") == (
        "https://example.test/coyote3/reset-password?token=abc"
    )
    assert password_flows._token_hash("abc") == password_flows._token_hash("abc")

    password_runtime["PASSWORD_TOKEN_TTL_SECONDS"] = object()
    assert password_flows._password_token_ttl_seconds() == 3600
    password_runtime["PASSWORD_TOKEN_TTL_SECONDS"] = 120
    password_runtime["PUBLIC_BASE_URL"] = ""
    assert password_flows._build_set_password_url("abc") == "/reset-password?token=abc"

    token = password_flows._issue_token(user_id="local.user", purpose="invite")
    assert password_flows._decode_password_token(token)["uid"] == "local.user"
    assert password_flows._decode_password_token("not-a-token") is None


@pytest.mark.parametrize(
    ("email", "configured", "sent", "warning"),
    [
        ("", True, True, "User email is missing."),
        ("user@example.test", False, False, "Mail is not configured."),
        ("user@example.test", True, False, "Mail send failed."),
        ("user@example.test", True, True, None),
    ],
)
def test_notify_user_change_reports_mail_outcome(
    password_runtime, monkeypatch, email, configured, sent, warning
):
    monkeypatch.setattr(password_flows, "smtp_configured", lambda _config: configured)
    monkeypatch.setattr(password_flows, "send_email", lambda **_kwargs: sent)

    result = password_flows.notify_user_change(
        user_doc={"username": "local.user", "email": email},
        event="profile_updated",
        actor_username="admin",
        changed_fields=["first_name", ""],
    )

    assert result == {
        "email_sent": bool(email and sent),
        "mail_configured": configured,
        "warning": warning,
    }


def test_issue_password_token_rejects_unknown_purpose(password_runtime):
    with pytest.raises(ValueError, match="Unsupported password token purpose"):
        password_flows.issue_password_token_for_user(login_identifier="user", purpose="delete")


@pytest.mark.parametrize(
    "user",
    [
        None,
        {"username": "disabled", "is_active": False, "auth_type": ["local"]},
        {"username": "ldap.user", "is_active": True, "auth_type": ["ldap"]},
    ],
)
def test_issue_password_token_is_neutral_for_unavailable_users(password_runtime, monkeypatch, user):
    monkeypatch.setattr(password_flows, "_lookup_user_doc", lambda *_args, **_kwargs: user)
    monkeypatch.setattr(password_flows, "smtp_configured", lambda _config: False)

    result = password_flows.issue_password_token_for_user(
        login_identifier="unknown", purpose="reset"
    )

    assert result == {"status": "ok", "email_sent": False, "mail_configured": False}


def test_issue_password_token_handles_missing_identity(password_runtime, monkeypatch):
    monkeypatch.setattr(
        password_flows,
        "_lookup_user_doc",
        lambda *_args, **_kwargs: {"is_active": True, "auth_type": ["local"]},
    )
    monkeypatch.setattr(password_flows, "resolve_user_identity", lambda _user: "")
    monkeypatch.setattr(password_flows, "smtp_configured", lambda _config: True)

    result = password_flows.issue_password_token_for_user(
        login_identifier="unknown", purpose="invite"
    )

    assert result["status"] == "ok"
    assert result["email_sent"] is False


def test_issue_password_token_persists_and_returns_manual_url(password_runtime, monkeypatch):
    repository = _UserRepository()
    monkeypatch.setattr(
        password_flows,
        "_lookup_user_doc",
        lambda *_args, **_kwargs: {
            "username": "local.user",
            "email": "user@example.test",
            "is_active": True,
            "auth_type": ["local"],
        },
    )
    monkeypatch.setattr(password_flows, "resolve_user_identity", lambda _user: "local.user")
    monkeypatch.setattr(password_flows, "get_user_repository", lambda: repository)
    monkeypatch.setattr(password_flows, "smtp_configured", lambda _config: False)
    monkeypatch.setattr(password_flows, "send_email", lambda **_kwargs: False)

    result = password_flows.issue_password_token_for_user(
        login_identifier="local.user", purpose="invite", actor_username="admin"
    )

    assert repository.issued["user_id"] == "local.user"
    assert repository.issued["purpose"] == "invite"
    assert repository.issued["issued_by"] == "admin"
    assert result["setup_url"].startswith("https://example.test/coyote3/reset-password?token=")
    assert result["expires_in_seconds"] == 120
    assert result["warning"] == "Mail is not configured. Share the setup URL manually."


@pytest.mark.parametrize(
    ("payload", "user", "token_valid", "error"),
    [
        (None, None, True, "Invalid or expired token"),
        ({"uid": "", "purpose": "reset"}, None, True, "Invalid token payload"),
        ({"uid": "user", "purpose": "other"}, None, True, "Invalid token payload"),
        (
            {"uid": "user", "purpose": "reset"},
            {"username": "user", "is_active": False, "auth_type": ["local"]},
            True,
            "Invalid token user",
        ),
        (
            {"uid": "user", "purpose": "reset"},
            {"username": "user", "is_active": True, "auth_type": ["local"]},
            False,
            "Token already used or expired",
        ),
    ],
)
def test_consume_password_token_rejects_invalid_states(
    password_runtime, monkeypatch, payload, user, token_valid, error
):
    repository = _UserRepository(user)
    repository.token_valid = token_valid
    monkeypatch.setattr(password_flows, "_decode_password_token", lambda _token: payload)
    monkeypatch.setattr(password_flows, "get_user_repository", lambda: repository)

    result = password_flows.consume_password_token_and_set_password(
        token="token", new_password="new-password"
    )

    assert result == {"status": "error", "error": error}


def test_consume_password_token_sets_password(password_runtime, monkeypatch):
    repository = _UserRepository(
        {"username": "user", "email": "", "is_active": True, "auth_type": ["local"]}
    )
    monkeypatch.setattr(
        password_flows,
        "_decode_password_token",
        lambda _token: {"uid": "USER", "purpose": "reset"},
    )
    monkeypatch.setattr(password_flows, "get_user_repository", lambda: repository)
    monkeypatch.setattr(password_flows.util.common, "hash_password", lambda value: f"hash:{value}")
    monkeypatch.setattr(
        password_flows,
        "notify_user_change",
        lambda **_kwargs: {"email_sent": True},
    )

    result = password_flows.consume_password_token_and_set_password(
        token="token", new_password="new-password"
    )

    assert repository.password_update["password_hash"] == "hash:new-password"
    assert result == {
        "status": "ok",
        "username": "user",
        "notification_email_sent": True,
    }


def test_change_local_password_rejects_user_and_provider(password_runtime, monkeypatch):
    repository = _UserRepository(None)
    monkeypatch.setattr(password_flows, "get_user_repository", lambda: repository)
    assert (
        password_flows.change_local_password(
            user_id="missing", current_password="old", new_password="new"
        )["error"]
        == "User not found"
    )

    repository.user = {"username": "ldap", "is_active": True, "auth_type": ["ldap"]}
    assert (
        password_flows.change_local_password(
            user_id="ldap", current_password="old", new_password="new"
        )["error"]
        == "Password is managed by external identity provider"
    )


def test_change_local_password_checks_current_password_and_updates(password_runtime, monkeypatch):
    repository = _UserRepository(
        {
            "username": "user",
            "password": "stored",
            "is_active": True,
            "auth_type": ["local"],
        }
    )
    monkeypatch.setattr(password_flows, "get_user_repository", lambda: repository)

    from api.domain.core.models.user import UserModel

    monkeypatch.setattr(UserModel, "validate_login", lambda _stored, current: current == "old")
    assert (
        password_flows.change_local_password(
            user_id="user", current_password="wrong", new_password="new"
        )["error"]
        == "Current password is incorrect"
    )

    monkeypatch.setattr(password_flows.util.common, "hash_password", lambda value: f"hash:{value}")
    monkeypatch.setattr(
        password_flows,
        "notify_user_change",
        lambda **_kwargs: {"email_sent": False},
    )
    result = password_flows.change_local_password(
        user_id="user", current_password="old", new_password="new"
    )
    assert repository.password_update["password_hash"] == "hash:new"
    assert result["status"] == "ok"
