"""HTTP permission and response-contract checks for assay setup administration."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.deps.services import get_assay_setup_service
from api.interfaces.http.admin.resources.assay_setup import router
from api.security.access import ApiUser


@pytest.fixture
def client(monkeypatch):
    """Run only the setup router with authenticated synthetic users and no database."""
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
    now = datetime.now(timezone.utc)
    doc = dict(
        _id="a" * 24,
        asp_id="assay_1",
        content=dict(
            panel=dict(
                asp_id="assay_1",
                asp_group="hematology",
                asp_family="panel-dna",
                asp_category="dna",
                display_name="Test",
            )
        ),
        revision=1,
        status="draft",
        content_editors=["author"],
        created_by="author",
        updated_by="author",
        created_at=now,
        updated_at=now,
    )
    service = SimpleNamespace(
        list_payload=lambda: {"items": []},
        get=lambda _: doc,
        save=lambda *_, **__: doc,
        transition=lambda *_, **__: doc,
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_assay_setup_service] = lambda: service
    with TestClient(app) as http:
        yield http, user, doc


def test_read_permission_is_not_write_permission(client):
    http, user, doc = client
    user.permissions = ["assay.panel:list", "assay.panel:view"]
    assert http.get("/api/v1/admin/assay-setups").status_code == 200
    assert http.post("/api/v1/admin/assay-setups", json=doc["content"]).status_code == 403


@pytest.mark.parametrize(
    "missing",
    ["assay.panel:create", "assay.panel:edit", "assay.config:create", "gene_list.insilico:create"],
)
def test_activation_requires_each_resource_permission(client, missing):
    http, user, _ = client
    user.permissions = [
        p
        for p in [
            "assay.panel:create",
            "assay.panel:edit",
            "assay.config:create",
            "gene_list.insilico:create",
        ]
        if p != missing
    ]
    assert (
        http.post("/api/v1/admin/assay-setups/test/publish", json={"revision": 1}).status_code
        == 403
    )


def test_create_returns_canonical_base_and_accepts_response_counts(client):
    http, user, doc = client
    user.permissions = ["assay.panel:create", "assay.config:create", "gene_list.insilico:create"]
    result = http.post("/api/v1/admin/assay-setups", json=doc["content"])
    assert result.status_code == 201
    assert result.json()["content"]["scopes"] == ["base"]
    # Derived gene counts in a response must not break subsequent form submissions.
    assert http.post("/api/v1/admin/assay-setups", json=result.json()["content"]).status_code == 201
