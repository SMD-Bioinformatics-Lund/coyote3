"""HTTP authentication and server-owned deployment data installation boundaries."""

from unittest.mock import Mock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from api.app.deps.application import get_installation
from api.interfaces.http.v1.admin.deployment_data import router
from api.security import access
from api.services.installation import Installation
from api.services.provisioning.deployment_data import DeploymentDataService
from coyote3.domain.exceptions import AppError
from tests.fixtures.api import application_sdk as sdk_fixtures
from tests.fixtures.api.mock_collections import api_user


@pytest.fixture
def boundary(monkeypatch):
    """Keep route and application authorization real while isolating storage and sessions."""
    user = api_user()
    user.roles = ["sys_admin"]
    repository, loader = Mock(), Mock(return_value={})
    repository.pending.return_value = ["assay_groups"]
    repository.install.return_value = {"assay_groups": "loaded"}

    def decode(request):
        if not request.headers.get("Authorization"):
            raise HTTPException(401, "Authentication required")
        return user

    monkeypatch.setattr(access, "_decode_session_user", decode)
    monkeypatch.setattr(access, "_audit_access_event", lambda **kwargs: None)
    service = DeploymentDataService(repository, loader)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_installation] = lambda: sdk_fixtures.authorized_operations(
        Installation, service, user
    )

    @app.exception_handler(AppError)
    async def app_error(request, error):
        return JSONResponse(status_code=error.status_code, content=error.detail)

    with TestClient(app) as client:
        yield client, user, repository, loader


def test_installation_has_no_public_data_endpoint(boundary):
    client, _, repository, loader = boundary
    result = client.get("/api/v1/public/installation/status?scope=application")
    assert result.status_code == 404
    assert not repository.mock_calls
    repository.install.assert_not_called()
    loader.assert_not_called()


def test_anonymous_cannot_add_data(boundary):
    client, _, repository, loader = boundary
    assert client.post("/api/v1/admin/installation/data", json={}).status_code == 401
    assert not repository.mock_calls
    loader.assert_not_called()


@pytest.mark.parametrize("role", ["viewer", "admin", "sys_admin", "superuser"])
def test_only_administrative_roles_can_add_data(boundary, role):
    client, user, repository, loader = boundary
    user.roles = [role]
    response = client.post(
        "/api/v1/admin/installation/data",
        headers={"Authorization": "Bearer synthetic"},
        json={"modules": ["application"]},
    )
    assert response.status_code == (403 if role == "viewer" else 200)
    if role == "viewer":
        assert not repository.mock_calls
        loader.assert_not_called()
    else:
        assert response.json() == {"collections": {"assay_groups": "loaded"}}
        assert repository.install.call_args.kwargs["actor"] == user.username


@pytest.mark.parametrize(
    "payload",
    [
        {"modules": ["invalid"]},
        {"force": True},
        {"modules": []},
        {"modules": ["application", "application"]},
        {"actor": "spoofed"},
        {"reference_dir": "/tmp/untrusted"},
        {"username": "admin", "roles": ["superuser"]},
    ],
)
def test_caller_cannot_supply_provenance_roles_or_seed_paths(boundary, payload):
    client, _, repository, loader = boundary
    response = client.post(
        "/api/v1/admin/installation/data",
        headers={"Authorization": "Bearer synthetic"},
        json=payload,
    )
    assert response.status_code == 422
    assert not repository.mock_calls
    loader.assert_not_called()


def test_initial_admin_must_change_password_before_any_maintenance(boundary):
    client, user, repository, loader = boundary
    user.must_change_password = True
    assert (
        client.post(
            "/api/v1/admin/installation/data",
            headers={"Authorization": "Bearer synthetic"},
            json={"modules": ["application"], "force": True},
        ).status_code
        == 403
    )
    user.roles = ["viewer"]
    assert (
        client.post(
            "/api/v1/admin/installation/data",
            headers={"Authorization": "Bearer synthetic"},
            json={"modules": ["application"]},
        ).status_code
        == 403
    )
    assert not repository.mock_calls
    loader.assert_not_called()
