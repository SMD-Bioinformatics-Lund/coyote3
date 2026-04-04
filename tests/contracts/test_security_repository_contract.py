"""Repository contract tests for security persistence adapters."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from api.infra.repositories.security_mongo import UserRepository


class _RolesHandler:
    def get_role(self, role_id):
        return {"role_id": role_id, "name": "analyst"}

    def get_all_roles(self):
        return [{"role_id": "r1"}]


class _AspHandler:
    def get_all_asps(self, is_active=True):
        return [{"asp_id": "asp1", "is_active": is_active}]


class _UserHandler:
    def __init__(self):
        self.last_login_updates = []
        self.password_tokens = []
        self.password_sets = []

    def user(self, username):
        return {"username": username}

    def user_with_id(self, user_id):
        return {"_id": user_id}

    def update_user_last_login(self, user_id):
        self.last_login_updates.append(user_id)

    def set_password_action_token(self, **kwargs):
        self.password_tokens.append(kwargs)

    def validate_and_clear_password_action_token(self, **kwargs):
        self.password_tokens.append({"validated": kwargs})
        return True

    def set_local_password(self, **kwargs):
        self.password_sets.append(kwargs)


class _SampleHandler:
    def get_sample(self, sample_id):
        return {"sample_id": sample_id, "kind": "sample"}

    def get_sample_by_id(self, sample_id):
        return {"_id": sample_id, "kind": "sample_by_id"}


def test_security_repository_contract(monkeypatch):
    user_handler = _UserHandler()
    store_stub = SimpleNamespace(
        roles_handler=_RolesHandler(),
        asp_handler=_AspHandler(),
        user_handler=user_handler,
        sample_handler=_SampleHandler(),
    )
    monkeypatch.setattr("api.infra.repositories.security_mongo.store", store_stub)

    repo = UserRepository()
    expires_at = datetime.now(timezone.utc)

    assert repo.get_role(None) is None
    assert repo.get_role("r1") == {"role_id": "r1", "name": "analyst"}
    assert repo.get_all_roles() == [{"role_id": "r1"}]
    assert repo.get_all_active_asps() == [{"asp_id": "asp1", "is_active": True}]
    assert repo.get_user_by_username("alice") == {"username": "alice"}
    assert repo.get_user_by_id("u1") == {"_id": "u1"}
    assert repo.get_sample("S1") == {"sample_id": "S1", "kind": "sample"}
    assert repo.get_sample_by_id("S1") == {"_id": "S1", "kind": "sample_by_id"}

    repo.update_user_last_login("u1")
    assert user_handler.last_login_updates == ["u1"]

    repo.set_user_password_token(
        user_id="u1",
        token_hash="hash",
        purpose="reset",
        expires_at=expires_at,
        issued_by="admin",
    )
    assert user_handler.password_tokens[0] == {
        "user_id": "u1",
        "token_hash": "hash",
        "purpose": "reset",
        "expires_at": expires_at,
        "issued_by": "admin",
    }

    assert repo.validate_and_clear_password_token(
        user_id="u1",
        token_hash="hash",
        purpose="reset",
    )

    repo.set_local_password(
        user_id="u1",
        password_hash="pw-hash",
        require_password_change=True,
    )
    assert user_handler.password_sets == [
        {
            "user_id": "u1",
            "password_hash": "pw-hash",
            "require_password_change": True,
        }
    ]
