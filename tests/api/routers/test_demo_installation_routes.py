"""Authorization and OpenAPI visibility of administrative demo installation."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.deps.services import get_demo_installation_service
from api.interfaces.http.admin.operations import router
from api.security import access
from tests.fixtures.api.mock_collections import api_user


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", ""),
        ("POST", "/configuration"),
        ("POST", "/samples/demo_group_dna"),
    ],
)
def test_demo_routes_require_permission_and_are_not_documented(monkeypatch, method, path):
    user = api_user()
    user.roles = []
    user.permissions = []
    monkeypatch.setattr(access, "_decode_session_user", lambda request: user)
    monkeypatch.setattr(access, "_audit_access_event", lambda **kwargs: None)
    monkeypatch.setattr(access, "get_roles_repository", lambda: None)
    monkeypatch.setattr(access, "get_permissions_repository", lambda: None)
    monkeypatch.setattr(
        access,
        "build_access_policy",
        lambda **kwargs: SimpleNamespace(
            permission_allowed=lambda candidate, permission, **options: (
                permission in candidate.permissions
            ),
        ),
    )
    service = Mock()
    service.plan.return_value = {
        "configuration": {},
        "configuration_installed": False,
        "samples": [],
    }
    service.install_configuration.return_value = {"status": "installed"}
    service.install_sample.return_value = {"status": "installed"}
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_demo_installation_service] = lambda: service
    with TestClient(app) as client:
        assert client.request(method, "/api/v1/admin/demo-installation" + path).status_code == 403
        assert not service.method_calls
        user.permissions = ["demo:install"]
        assert client.request(method, "/api/v1/admin/demo-installation" + path).status_code == 200
        assert not any("demo-installation" in route for route in app.openapi()["paths"])
