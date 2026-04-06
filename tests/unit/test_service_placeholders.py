"""Coverage tests for thin service wrappers and placeholders."""

from __future__ import annotations

from types import SimpleNamespace

from api.security.auth_service import authenticate_credentials
from api.services.accounts.user_profile import UserService
from api.services.sample.sample_lookup import SampleService


def test_auth_service_authenticate_credentials_importable():
    assert callable(authenticate_credentials)


def test_sample_service_delegates_update_filters(monkeypatch):
    class _Repo:
        def __init__(self):
            self.called = None

        def update_sample_filters(self, sample_id, filters):
            self.called = (sample_id, filters)

    repo = _Repo()
    SampleService(sample_handler=repo).update_filters("S1", {"a": 1})
    assert repo.called == ("S1", {"a": 1})


def test_user_service_delegates_get_user_by_id(monkeypatch):
    class _Repo:
        def get_user_by_id(self, user_id):
            return {"_id": user_id}

    payload = UserService(
        user_handler=SimpleNamespace(user_with_id=_Repo().get_user_by_id)
    ).get_user_by_id("u1")
    assert payload["_id"] == "u1"
