"""Tests for auth service identity lookup behavior."""

from __future__ import annotations

from api.security import auth_service


class _FakeRepo:
    def __init__(self, by_username=None, by_id=None):
        self.by_username = by_username
        self.by_id = by_id
        self.calls = []

    def get_user_by_username(self, username):
        self.calls.append(("username", username))
        return self.by_username

    def get_user_by_id(self, user_id):
        self.calls.append(("id", user_id))
        return self.by_id


def test_lookup_user_doc_tries_username_then_id(monkeypatch):
    repo = _FakeRepo(by_username=None, by_id={"_id": "u1"})
    monkeypatch.setattr(auth_service, "get_security_repository", lambda: repo)

    user_doc = auth_service._lookup_user_doc("tester")

    assert user_doc == {"_id": "u1"}
    assert repo.calls == [("username", "tester"), ("id", "tester")]


def test_lookup_user_doc_skips_id_when_username_hit(monkeypatch):
    repo = _FakeRepo(by_username={"_id": "u2"}, by_id={"_id": "u1"})
    monkeypatch.setattr(auth_service, "get_security_repository", lambda: repo)

    user_doc = auth_service._lookup_user_doc("tester")

    assert user_doc == {"_id": "u2"}
    assert repo.calls == [("username", "tester")]


def test_resolve_user_identity_prefers_business_key():
    assert auth_service.resolve_user_identity({"user_id": "coyote3.admin", "_id": "legacy"}) == "coyote3.admin"
    assert auth_service.resolve_user_identity({"_id": "legacy"}) == ""
