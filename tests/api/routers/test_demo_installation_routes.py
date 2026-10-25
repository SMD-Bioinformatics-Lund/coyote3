"""Authorization and OpenAPI visibility of administrative demo installation."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.deps.application import get_installation
from api.interfaces.http.v1.admin.operations import router
from api.security import access
from api.services.installation import Installation
from tests.fixtures.api import application_sdk as sdk_fixtures
from tests.fixtures.api.mock_collections import api_user


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", ""),
        ("POST", "/configuration"),
        ("POST", "/starter"),
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
    service.install_starter.return_value = {"status": "installed"}
    service.install_sample.return_value = {"status": "installed"}
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_installation] = lambda: sdk_fixtures.authorized_operations(
        Installation, service, user
    )
    with TestClient(app) as client:
        assert client.request(method, "/api/v1/admin/demo-installation" + path).status_code == 403
        assert not service.method_calls
        user.permissions = ["demo:install"]
        assert client.request(method, "/api/v1/admin/demo-installation" + path).status_code == 200
        assert not any("demo-installation" in route for route in app.openapi()["paths"])
        service.reset_mock()
        user.permissions = []
        user.roles = ["superuser"]
        assert client.request(method, "/api/v1/admin/demo-installation" + path).status_code == 200


def test_only_installation_roles_receive_demo_permission():
    """Clinical group membership alone never grants installation privileges."""
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[3] / "api/bootstrap/catalogs/rbac/roles.seed.ndjson"
    roles = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    assert {role["role_id"] for role in roles if "demo:install" in role["permissions"]} == {
        "demo_installer",
        "admin",
        "sys_admin",
        "superuser",
    }
    demo = next(role for role in roles if role["role_id"] == "demo_installer")
    assert demo["permissions"] == ["demo:install"]
