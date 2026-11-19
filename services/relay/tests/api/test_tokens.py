"""Relay HTTP routes retain host-owned machine credential restrictions."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from coyote_api.app.deps import services
from coyote_api.security import access
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from coyote_relay.api import routes as internal


@pytest.fixture
def token_policy(monkeypatch):
    monkeypatch.setattr(access, "get_internal_api_token", lambda config: "synthetic-internal-token")
    monkeypatch.setattr(access.runtime_app, "config", {"ENV_NAME": "development"})
    monkeypatch.setattr(
        access, "get_roles_repository", lambda: SimpleNamespace(get_all_roles=lambda: [])
    )
    monkeypatch.setattr(
        access,
        "get_permissions_repository",
        lambda: SimpleNamespace(
            get_all_permissions=lambda **kwargs: [
                {"permission_id": p}
                for p in ["internal.ingest:manage", "sample:edit:own", "user:create"]
            ]
        ),
    )


def test_upload_accepts_internal_token_but_collection_routes_do_not(token_policy, monkeypatch):
    monkeypatch.setattr(
        services,
        "get_app_controls_service",
        lambda: SimpleNamespace(module_enabled=lambda _key: True),
    )
    app = FastAPI()
    app.include_router(internal.router)
    result = {
        "status": "ok",
        "sample_id": "synthetic",
        "sample_name": "synthetic",
        "written": {},
        "data_counts": {},
    }
    service = SimpleNamespace(ingest_sample_bundle=lambda *a, **kw: result)
    monkeypatch.setattr(services, "get_internal_ingest_service", lambda: service)
    monkeypatch.setattr(
        services, "get_audit_service", lambda: SimpleNamespace(record=Mock(return_value="audit-id"))
    )
    monkeypatch.setattr(
        "coyote.application.ingest.upload_bundle.prepare_uploaded_bundle",
        lambda **kw: {"asp_id": "synthetic", "environment": "production"},
    )
    monkeypatch.setattr(
        access,
        "_decode_session_user",
        lambda req: (_ for _ in ()).throw(HTTPException(401, "Login required")),
    )
    monkeypatch.setattr(access, "_audit_access_event", lambda **kwargs: None)
    client = TestClient(app)
    headers = {"X-Coyote-Internal-Token": "synthetic-internal-token"}
    response = client.post(
        "/api/v1/internal/ingest/sample-bundle/upload",
        headers=headers,
        files={"yaml_file": ("synthetic.yaml", "name: synthetic")},
        data={"acknowledge": "true"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    response = client.get("/api/v1/internal/tasks/synthetic", headers=headers)
    assert response.status_code == 401
