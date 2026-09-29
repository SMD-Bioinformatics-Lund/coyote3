"""Assay group permission gates, request validation and audit traceability."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.deps.services import get_admin_assay_group_service
from api.application.resources.assay_groups import AssayGroupService
from api.interfaces.http.admin.resources.asp import router
from api.security.access import ApiUser


@pytest.fixture
def client(monkeypatch):
    """Run isolated authenticated routes without connecting to any database."""
    user = ApiUser(
        id="test",
        username="author",
        email="author@example.invalid",
        fullname="Test",
        roles=["test-role"],
        role="test-role",
        access_level=0,
        permissions=[],
        asp_ids=[],
        asp_groups=[],
        envs=[],
        asp_map={},
        auth_type=["local"],
    )
    monkeypatch.setattr("api.security.access._decode_session_user", lambda _: user)
    monkeypatch.setattr("api.security.access._audit_access_event", lambda **_: None)
    monkeypatch.setattr("api.security.access.get_permissions_repository", lambda: None)
    monkeypatch.setattr(
        "api.security.access.get_roles_repository",
        lambda: SimpleNamespace(
            get_all_roles=lambda: [
                {"role_id": "test-role", "is_active": True, "permissions": user.permissions}
            ]
        ),
    )
    group = {
        "group_id": "demo",
        "display_name": "Demo",
        "system_managed": True,
        "is_active": True,
        "version": 1,
        "created_by": "system",
        "created_on": datetime.now(timezone.utc),
    }
    service = AssayGroupService(
        SimpleNamespace(
            list=lambda: [],
            create=lambda document: None,
            get=lambda key: group if key == "demo" else None,
            affected_assays=lambda _: ["demo-assay"],
            change_status=lambda *args, **kwargs: group,
        )
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_admin_assay_group_service] = lambda: service
    with TestClient(app) as http:
        yield http, user


def test_view_permission_does_not_allow_group_creation(client):
    http, user = client
    assert http.get("/api/v1/resources/assay-groups").status_code == 403
    user.permissions = ["assay.panel:view"]
    assert (
        http.patch(
            "/api/v1/resources/assay-groups/demo/status",
            json={
                "is_active": False,
                "expected_version": 1,
                "reason": "Pause",
            },
        ).status_code
        == 403
    )
    assert http.get("/api/v1/resources/assay-groups").json() == {"groups": []}
    assert (
        http.post(
            "/api/v1/resources/assay-groups", json={"group_id": "custom", "display_name": "Custom"}
        ).status_code
        == 403
    )


def test_ownership_cannot_be_supplied_and_no_mutation_routes_exist(client):
    http, user = client
    user.permissions = ["assay.panel:edit"]
    assert (
        http.post(
            "/api/v1/resources/assay-groups",
            json={"group_id": "custom", "display_name": "Custom", "system_managed": True},
        ).status_code
        == 422
    )
    for method in (http.put, http.patch, http.delete):
        assert method("/api/v1/resources/assay-groups/solid").status_code in (404, 405)


def test_editor_can_create_custom_group(client):
    http, user = client
    user.permissions = ["assay.panel:edit"]
    response = http.post(
        "/api/v1/resources/assay-groups",
        json={"group_id": "custom", "display_name": "Custom"},
    )
    assert response.status_code == 201
    assert response.json()["resource_id"] == "custom"


def test_status_requires_reason_and_revision(client):
    http, user = client
    user.permissions = ["assay.panel:edit"]
    for payload in (
        {"is_active": False},
        {"is_active": False, "expected_version": 1, "reason": " "},
    ):
        assert (
            http.patch("/api/v1/resources/assay-groups/demo/status", json=payload).status_code
            == 422
        )


def test_impact_and_status_response_contracts(client):
    http, user = client
    user.permissions = ["assay.panel:view", "assay.panel:edit"]
    impact = http.get("/api/v1/resources/assay-groups/demo/impact")
    assert impact.status_code == 200
    assert impact.json()["assays"] == ["demo-assay"]
    response = http.patch(
        "/api/v1/resources/assay-groups/demo/status",
        json={
            "is_active": False,
            "expected_version": 1,
            "reason": "Pause new work",
        },
    )
    assert response.status_code == 200
    assert response.json()["meta"]["revision"]["new_version"] == 2


def test_creation_attaches_audit_identity():
    from starlette.requests import Request

    from api.contracts.schemas.assay_groups import AssayGroupCreate
    from api.interfaces.http.admin.resources.asp import create_assay_group

    request = Request({"type": "http"})
    actors = []

    def create(payload, *, actor):
        actors.append(actor)
        return {"resource_id": payload.group_id, "meta": {}}

    create_assay_group(
        request=request,
        payload=AssayGroupCreate(group_id="custom", display_name="Custom"),
        user=SimpleNamespace(username="author"),
        service=SimpleNamespace(create=create),
    )
    assert actors == ["author"]
    assert request.state.audit_resource["id"] == "custom"
    assert request.state.audit_resource["retention_class"] == "traceability"
