"""Tests for auth service identity lookup behavior."""

from __future__ import annotations

from types import SimpleNamespace

from api.security import auth_service


class _FakeRepo:
    """Provide  FakeRepo behavior."""

    def __init__(self, by_username=None, by_id=None):
        """Handle __init__.

        Args:
                by_username: By username. Optional argument.
                by_id: By id. Optional argument.
        """
        self.by_username = by_username
        self.by_id = by_id
        self.calls = []

    def get_user_by_username(self, username):
        """Return user by username.

        Args:
            username: Value for ``username``.

        Returns:
            The function result.
        """
        self.calls.append(("username", username))
        return self.by_username

    def get_user_by_id(self, user_id):
        """Return user by id.

        Args:
            user_id: Value for ``user_id``.

        Returns:
            The function result.
        """
        self.calls.append(("id", user_id))
        return self.by_id


def test_lookup_user_doc_tries_username_then_id(monkeypatch):
    """Handle test lookup user doc tries username then id.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    repo = _FakeRepo(by_username=None, by_id={"_id": "u1"})
    monkeypatch.setattr(auth_service, "get_security_repository", lambda: repo)

    user_doc = auth_service._lookup_user_doc("tester")

    assert user_doc == {"_id": "u1"}
    assert repo.calls == [("username", "tester"), ("id", "tester")]


def test_lookup_user_doc_skips_id_when_username_hit(monkeypatch):
    """Handle test lookup user doc skips id when username hit.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    repo = _FakeRepo(by_username={"_id": "u2"}, by_id={"_id": "u1"})
    monkeypatch.setattr(auth_service, "get_security_repository", lambda: repo)

    user_doc = auth_service._lookup_user_doc("tester")

    assert user_doc == {"_id": "u2"}
    assert repo.calls == [("username", "tester")]


def test_resolve_user_identity_prefers_business_key():
    """Handle test resolve user identity prefers business key.

    Returns:
        The function result.
    """
    assert (
        auth_service.resolve_user_identity({"username": "coyote3.admin", "_id": "legacy"})
        == "coyote3.admin"
    )
    assert auth_service.resolve_user_identity({"_id": "legacy"}) == ""


def test_local_auth_allowlist_matches_identifier_username_or_email(monkeypatch):
    """Allowlist matching uses login id, username, and email candidates."""
    monkeypatch.setattr(
        auth_service,
        "app",
        SimpleNamespace(config={"LOCAL_AUTH_USER_IDENTIFIERS": ("admin", "admin@example.com")}),
    )

    assert auth_service._is_local_auth_allowlisted("admin", {"username": "u", "email": "x"}) is True
    assert (
        auth_service._is_local_auth_allowlisted(
            "ignored", {"username": "admin", "email": "not-matching@example.com"}
        )
        is True
    )
    assert (
        auth_service._is_local_auth_allowlisted(
            "ignored", {"username": "not-matching", "email": "admin@example.com"}
        )
        is True
    )
    assert (
        auth_service._is_local_auth_allowlisted(
            "ignored", {"username": "nope", "email": "nope@example.com"}
        )
        is False
    )


def test_ldap_authenticate_uses_configured_base_dn_and_attr(monkeypatch):
    """LDAP auth forwards app config values to ldap manager."""
    calls = {}

    def _auth(**kwargs):
        calls.update(kwargs)
        return {"dn": "uid=user"}

    monkeypatch.setattr(auth_service.ldap_manager, "authenticate", _auth)
    monkeypatch.setattr(
        auth_service,
        "app",
        SimpleNamespace(
            config={"LDAP_BASE_DN": "dc=example,dc=com", "LDAP_USER_LOGIN_ATTR": "mail"}
        ),
    )

    assert auth_service._ldap_authenticate("user@example.com", "secret") is True
    assert calls["username"] == "user@example.com"
    assert calls["password"] == "secret"
    assert calls["base_dn"] == "dc=example,dc=com"
    assert calls["attribute"] == "mail"


def test_build_user_session_payload_maps_user_model(monkeypatch):
    """Session payload delegates to repository + UserModel mapping."""
    repo = SimpleNamespace(
        get_role=lambda _role_name: {"role_id": "admin", "permissions": []},
        get_all_active_asps=lambda: [{"asp_id": "WGS"}],
    )
    monkeypatch.setattr(auth_service, "get_security_repository", lambda: repo)
    monkeypatch.setattr(
        auth_service.UserModel,
        "from_mongo",
        lambda user_doc, role_doc, asp_docs: SimpleNamespace(
            to_dict=lambda: {
                "username": user_doc["username"],
                "role": role_doc.get("role_id"),
                "asp_count": len(asp_docs),
            }
        ),
    )

    payload = auth_service.build_user_session_payload({"username": "tester", "role": "admin"})

    assert payload == {"username": "tester", "role": "admin", "asp_count": 1}


def test_authenticate_credentials_internal_auth_path(monkeypatch):
    """Internal auth validates password hash and returns user doc."""
    user_doc = {"username": "tester", "auth_type": "coyote3", "password": "HASH", "is_active": True}
    monkeypatch.setattr(auth_service, "_lookup_user_doc", lambda _username: user_doc)
    monkeypatch.setattr(auth_service, "_is_local_auth_allowlisted", lambda *_: False)
    monkeypatch.setattr(
        auth_service.UserModel,
        "validate_login",
        lambda hashed, raw: hashed == "HASH" and raw == "secret",
    )
    monkeypatch.setattr(auth_service, "_ldap_authenticate", lambda *_: False)

    assert auth_service.authenticate_credentials("tester", "secret") == user_doc
    assert auth_service.authenticate_credentials("tester", "wrong") is None


def test_authenticate_credentials_external_ldap_path(monkeypatch):
    """External auth uses LDAP when user is not internal/allowlisted."""
    user_doc = {"username": "tester", "auth_type": "ldap", "password": "HASH", "is_active": True}
    monkeypatch.setattr(auth_service, "_lookup_user_doc", lambda _username: user_doc)
    monkeypatch.setattr(auth_service, "_is_local_auth_allowlisted", lambda *_: False)
    monkeypatch.setattr(auth_service.UserModel, "validate_login", lambda *_: False)
    monkeypatch.setattr(
        auth_service,
        "_ldap_authenticate",
        lambda username, password: username == "tester" and password == "secret",
    )

    assert auth_service.authenticate_credentials("tester", "secret") == user_doc
    assert auth_service.authenticate_credentials("tester", "wrong") is None


def test_authenticate_credentials_uses_internal_path_when_allowlisted(monkeypatch):
    """Allowlisted users always follow internal auth path."""
    user_doc = {"username": "tester", "auth_type": "ldap", "password": "HASH", "is_active": True}
    monkeypatch.setattr(auth_service, "_lookup_user_doc", lambda _username: user_doc)
    monkeypatch.setattr(auth_service, "_is_local_auth_allowlisted", lambda *_: True)
    monkeypatch.setattr(auth_service.UserModel, "validate_login", lambda *_: True)
    monkeypatch.setattr(auth_service, "_ldap_authenticate", lambda *_: False)

    assert auth_service.authenticate_credentials("tester", "secret") == user_doc


def test_authenticate_credentials_rejects_missing_or_inactive_user(monkeypatch):
    """Auth rejects no-user and inactive-user states."""
    monkeypatch.setattr(auth_service, "_lookup_user_doc", lambda _username: None)
    assert auth_service.authenticate_credentials("tester", "secret") is None

    monkeypatch.setattr(
        auth_service,
        "_lookup_user_doc",
        lambda _username: {"username": "tester", "is_active": False},
    )
    assert auth_service.authenticate_credentials("tester", "secret") is None


def test_update_user_last_login_calls_repository(monkeypatch):
    """Last login update delegates to security repository."""
    calls = {}
    repo = SimpleNamespace(
        update_user_last_login=lambda user_id: calls.setdefault("user_id", user_id)
    )
    monkeypatch.setattr(auth_service, "get_security_repository", lambda: repo)

    auth_service.update_user_last_login("tester")

    assert calls["user_id"] == "tester"
