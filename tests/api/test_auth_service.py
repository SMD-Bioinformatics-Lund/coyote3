"""Tests for auth service identity lookup behavior."""

from __future__ import annotations

from types import SimpleNamespace

from api.domain.core.models.user import UserModel
from api.security import auth_service


class _FakeRepo:
    """Provide  FakeRepo behavior."""

    def __init__(self, by_username=None, by_email=None):
        """__init__.

        Args:
                by_username: By username. Optional argument.
        """
        self.by_username = by_username
        self.by_email = by_email
        self.calls = []

    def user_by_username(self, username):
        """Return user by username.

        Args:
            username: Value for ``username``.

        Returns:
            The function result.
        """
        self.calls.append(("username", username))
        return self.by_username

    def user_by_email(self, email):
        """Return user by email."""
        self.calls.append(("email", email))
        return self.by_email


def test_lookup_user_doc_uses_username_for_local_login(monkeypatch):
    """Username login uses username/local lookup.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    repo = _FakeRepo(by_username={"_id": "u1"})
    monkeypatch.setattr(auth_service, "get_user_repository", lambda: repo)

    user_doc = auth_service._lookup_user_doc("tester")

    assert user_doc == {"_id": "u1"}
    assert repo.calls == [("username", "tester")]


def test_lookup_user_doc_uses_email_for_ldap_login(monkeypatch):
    """Email login uses email/LDAP lookup.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    repo = _FakeRepo(by_email={"_id": "u2"})
    monkeypatch.setattr(auth_service, "get_user_repository", lambda: repo)

    user_doc = auth_service._lookup_user_doc("tester@example.com")

    assert user_doc == {"_id": "u2"}
    assert repo.calls == [("email", "tester@example.com")]


def test_resolve_user_identity_prefers_business_key():
    """Test resolve user identity prefers business key.

    Returns:
        The function result.
    """
    assert (
        auth_service.resolve_user_identity({"username": "coyote3.admin", "_id": "historical"})
        == "coyote3.admin"
    )
    assert auth_service.resolve_user_identity({"_id": "historical"}) == ""


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
    """Session payload delegates to store handlers + UserModel mapping."""
    store_stub = SimpleNamespace(
        roles_repository=SimpleNamespace(
            get_role=lambda _role_name: {"role_id": "admin", "permissions": []}
        ),
        assay_panel_repository=SimpleNamespace(
            get_all_asps=lambda is_active=True: [{"asp_id": "WGS"}]
        ),
    )
    monkeypatch.setattr(auth_service, "get_roles_repository", lambda: store_stub.roles_repository)
    monkeypatch.setattr(
        auth_service, "get_assay_panel_repository", lambda: store_stub.assay_panel_repository
    )
    monkeypatch.setattr(
        auth_service.UserModel,
        "from_auth_payload",
        lambda user_doc, role_docs, asp_docs: SimpleNamespace(
            to_dict=lambda: {
                "username": user_doc["username"],
                "roles": user_doc["roles"],
                "role": role_docs[0].get("role_id"),
                "asp_count": len(asp_docs),
            }
        ),
    )

    payload = auth_service.build_user_session_payload({"username": "tester", "roles": ["admin"]})

    assert payload == {
        "username": "tester",
        "roles": ["admin"],
        "role": "admin",
        "asp_count": 1,
    }


def test_user_model_from_auth_payload_accepts_local_email_domain():
    """Local center domains like .local should not break auth session serialization."""
    user_doc = {
        "_id": "u1",
        "email": "ADMIN@COYOTE3.LOCAL",
        "username": "admin",
        "fullname": "Admin User",
        "roles": ["admin"],
        "is_active": True,
    }

    model = UserModel.from_auth_payload(user_doc, [{"role_id": "admin", "level": 99}], [])

    assert model.email == "admin@coyote3.local"


def test_user_model_from_auth_payload_normalizes_role_permission_ids():
    """Role permission ids should be normalized on read."""
    user_doc = {
        "_id": "u1",
        "email": "admin@coyote3.local",
        "username": "admin",
        "fullname": "Admin User",
        "roles": ["admin"],
        "is_active": True,
    }

    model = UserModel.from_auth_payload(
        user_doc,
        [
            {
                "role_id": "admin",
                "level": 99,
                "permissions": [" Report:Preview ", "report:preview", "Sample:Edit:Global"],
            }
        ],
        [],
    )

    assert model.permissions == ["report:preview", "sample:edit:global"]


def test_authenticate_credentials_internal_auth_path(monkeypatch):
    """Internal auth validates password hash and returns user doc."""
    user_doc = {"username": "tester", "auth_type": ["local"], "password": "HASH", "is_active": True}
    monkeypatch.setattr(auth_service, "_lookup_user_doc", lambda *_args, **_kwargs: user_doc)
    monkeypatch.setattr(
        auth_service.UserModel,
        "validate_login",
        lambda hashed, raw: hashed == "HASH" and raw == "secret",
    )
    monkeypatch.setattr(auth_service, "_ldap_authenticate", lambda *_: False)

    assert auth_service.authenticate_credentials("tester", "secret") == user_doc
    assert auth_service.authenticate_credentials("tester", "wrong") is None


def test_authenticate_credentials_external_ldap_path(monkeypatch):
    """LDAP auth_type routes email authentication to LDAP validation."""
    user_doc = {
        "username": "tester",
        "email": "tester@example.com",
        "auth_type": ["ldap"],
        "password": "HASH",
        "is_active": True,
    }
    monkeypatch.setattr(auth_service, "_lookup_user_doc", lambda *_args, **_kwargs: user_doc)
    monkeypatch.setattr(auth_service.UserModel, "validate_login", lambda *_: False)
    monkeypatch.setattr(
        auth_service,
        "_ldap_authenticate",
        lambda username, password: username == "tester@example.com" and password == "secret",
    )

    assert auth_service.authenticate_credentials("tester@example.com", "secret") == user_doc
    assert auth_service.authenticate_credentials("tester@example.com", "wrong") is None


def test_authenticate_credentials_ldap_user_uses_ldap_path(monkeypatch):
    """LDAP users should not use local password validation."""
    user_doc = {"username": "tester", "auth_type": ["ldap"], "password": "HASH", "is_active": True}
    monkeypatch.setattr(auth_service, "_lookup_user_doc", lambda *_args, **_kwargs: user_doc)
    monkeypatch.setattr(auth_service.UserModel, "validate_login", lambda *_: False)
    monkeypatch.setattr(auth_service, "_ldap_authenticate", lambda *_: True)

    assert auth_service.authenticate_credentials("tester@example.com", "secret") == user_doc


def test_authenticate_credentials_mixed_provider_routes_by_identifier(monkeypatch):
    """Users with both providers can use email for LDAP and username for local."""
    user_doc = {
        "username": "tester",
        "email": "tester@example.com",
        "auth_type": ["local", "ldap"],
        "password": "HASH",
        "is_active": True,
    }
    monkeypatch.setattr(auth_service, "_lookup_user_doc", lambda *_args, **_kwargs: user_doc)
    monkeypatch.setattr(
        auth_service.UserModel,
        "validate_login",
        lambda hashed, raw: hashed == "HASH" and raw == "local-secret",
    )
    monkeypatch.setattr(
        auth_service,
        "_ldap_authenticate",
        lambda username, password: username == "tester@example.com" and password == "ldap-secret",
    )

    assert auth_service.authenticate_credentials("tester", "local-secret") == user_doc
    assert auth_service.authenticate_credentials("tester@example.com", "ldap-secret") == user_doc
    assert auth_service.authenticate_credentials("tester", "ldap-secret") is None
    assert auth_service.authenticate_credentials("tester@example.com", "local-secret") is None


def test_authenticate_credentials_ldap_only_rejects_username_login(monkeypatch):
    """LDAP-only users must login with email, not username."""
    user_doc = {
        "username": "tester",
        "email": "tester@example.com",
        "auth_type": ["ldap"],
        "password": "HASH",
        "is_active": True,
    }
    monkeypatch.setattr(auth_service, "_lookup_user_doc", lambda *_args, **_kwargs: user_doc)
    monkeypatch.setattr(auth_service.UserModel, "validate_login", lambda *_: True)
    monkeypatch.setattr(auth_service, "_ldap_authenticate", lambda *_: True)

    assert auth_service.authenticate_credentials("tester", "secret") is None
    assert auth_service.authenticate_credentials("tester@example.com", "secret") == user_doc


def test_authenticate_credentials_defaults_missing_auth_type_to_ldap(monkeypatch):
    """Users without explicit auth_type should use LDAP auth."""
    user_doc = {"username": "tester", "password": "HASH", "is_active": True}
    monkeypatch.setattr(auth_service, "_lookup_user_doc", lambda *_args, **_kwargs: user_doc)
    monkeypatch.setattr(auth_service.UserModel, "validate_login", lambda *_: True)
    monkeypatch.setattr(auth_service, "_ldap_authenticate", lambda *_: True)

    assert auth_service.authenticate_credentials("tester@example.com", "secret") == user_doc


def test_authenticate_credentials_rejects_missing_or_inactive_user(monkeypatch):
    """Auth rejects no-user and inactive-user states."""
    monkeypatch.setattr(auth_service, "_lookup_user_doc", lambda *_args, **_kwargs: None)
    assert auth_service.authenticate_credentials("tester", "secret") is None

    monkeypatch.setattr(
        auth_service,
        "_lookup_user_doc",
        lambda *_args, **_kwargs: {"username": "tester", "is_active": False},
    )
    assert auth_service.authenticate_credentials("tester", "secret") is None


def test_update_user_last_login_calls_user_repository(monkeypatch):
    """Last login update delegates to the user repository."""
    calls = {}
    user_repository = SimpleNamespace(
        update_user_last_login=lambda user_id: calls.setdefault("user_id", user_id)
    )
    monkeypatch.setattr(auth_service, "get_user_repository", lambda: user_repository)

    auth_service.update_user_last_login("tester")

    assert calls["user_id"] == "tester"
