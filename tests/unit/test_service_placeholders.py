"""Coverage tests for thin service wrappers and placeholders."""

from __future__ import annotations

import api.services.auth_service as auth_service
from api.services.sample_service import SampleService
from api.services.user_service import UserService
from api.services.variant_service import VariantService


def test_auth_service_module_exports():
    assert hasattr(auth_service, "authenticate_credentials")


def test_variant_service_placeholder_instantiates():
    service = VariantService()
    assert service.__class__.__name__ == "VariantService"


def test_sample_service_delegates_update_filters():
    class _Repo:
        def __init__(self):
            self.called = None

        def update_sample_filters(self, sample_id, filters):
            self.called = (sample_id, filters)

    repo = _Repo()
    SampleService(repository=repo).update_filters("S1", {"a": 1})
    assert repo.called == ("S1", {"a": 1})


def test_user_service_delegates_get_user_by_id():
    class _Repo:
        def get_user_by_id(self, user_id):
            return {"_id": user_id}

    payload = UserService(repository=_Repo()).get_user_by_id("u1")
    assert payload["_id"] == "u1"
