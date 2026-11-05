"""Version-history HTTP reads use existing view permissions and never write."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.deps.application import get_assay_configurations, get_assays, get_gene_lists
from api.interfaces.http.v1.admin.resources import asp, aspc, genelists
from api.security import access
from tests.fixtures.api.mock_collections import api_user


@pytest.mark.parametrize(
    ("module", "dependency", "kind", "permission"),
    [
        (asp, get_assays, "asp", "assay.panel:view"),
        (aspc, get_assay_configurations, "aspc", "assay.config:view"),
        (genelists, get_gene_lists, "genelists", "gene_list.insilico:view"),
    ],
)
def test_history_requires_view_permission_and_returns_retained_versions(
    monkeypatch, module, dependency, kind, permission
):
    """Denied callers cannot access history; permitted reads preserve every returned version."""
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
            permission_allowed=lambda candidate, required, **options: (
                required in candidate.permissions
            )
        ),
    )
    service = Mock()
    service.versions.return_value = [
        {"version": 2, "is_active": True},
        {"version": 1, "is_active": False},
    ]
    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[dependency] = lambda: service
    with TestClient(app) as client:
        path = f"/api/v1/resources/{kind}/synthetic/versions"
        assert client.get(path).status_code == 403
        service.versions.assert_not_called()
        user.permissions = [permission]
        response = client.get(path)
        assert response.status_code == 200
        assert response.json() == service.versions.return_value
        service.versions.assert_called_once_with(identifier="synthetic")
