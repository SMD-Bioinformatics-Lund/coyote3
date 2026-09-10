"""Require user authorization and durable audit for credential issuance."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.deps.services import get_audit_service
from api.interfaces.http.admin import operations
from api.security import access
from api.security.ingest_tokens import verify_token


@pytest.fixture
def issuance(monkeypatch):
    audit = Mock()
    audit.record.return_value = "synthetic-audit-id"
    monkeypatch.setattr(
        operations, "get_internal_api_token", lambda config: "synthetic-signing-key"
    )
    monkeypatch.setattr(operations.runtime_app, "config", {"ENV_NAME": "development"})
    monkeypatch.setattr(access, "_audit_access_event", lambda **kwargs: None)
    monkeypatch.setattr(
        access, "get_roles_repository", lambda: SimpleNamespace(get_all_roles=lambda: [])
    )
    monkeypatch.setattr(
        access,
        "get_permissions_repository",
        lambda: SimpleNamespace(
            get_all_permissions=lambda **kwargs: [
                {"permission_id": "ingest.token:issue", "is_active": True},
                {"permission_id": "internal.ingest:manage", "is_active": True},
            ]
        ),
    )
    app = FastAPI()
    app.include_router(operations.router)
    app.dependency_overrides[get_audit_service] = lambda: audit
    return TestClient(app), audit


def user_session(monkeypatch, permissions):
    """Provide a resolved user session while retaining real permission enforcement."""
    user = access.ApiUser(
        id="synthetic-issuer",
        username="issuer",
        email="",
        fullname="Issuer",
        role="issuer",
        access_level=0,
        asp_ids=[],
        asp_groups=[],
        asp_map={},
        auth_type=["local"],
        permissions=permissions,
        roles=["issuer"],
        envs=["development"],
    )
    monkeypatch.setattr(
        access,
        "get_roles_repository",
        lambda: SimpleNamespace(
            get_all_roles=lambda: [
                {"role_id": "issuer", "is_active": True, "permissions": permissions}
            ]
        ),
    )
    monkeypatch.setattr(
        access, "_get_cached_api_session", lambda request, token: SimpleNamespace(user=user)
    )
    monkeypatch.setattr(access, "_enforce_password_change", lambda user, request: None)


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-Coyote-Ingest-Token": "synthetic"}, {"X-Coyote-Internal-Token": "synthetic"}],
)
def test_machine_credentials_cannot_issue(issuance, headers):
    client, audit = issuance
    response = client.post("/api/v1/admin/ingest-tokens", headers=headers, json={})
    assert response.status_code == 401
    audit.record.assert_not_called()


def test_user_requires_dedicated_permission(issuance, monkeypatch):
    client, audit = issuance
    user_session(monkeypatch, ["internal.ingest:manage"])
    assert (
        client.post(
            "/api/v1/admin/ingest-tokens", headers={"Authorization": "Bearer synthetic"}, json={}
        ).status_code
        == 403
    )
    audit.record.assert_not_called()


def test_authorized_issuance_audits_without_recording_secret(issuance, monkeypatch):
    client, audit = issuance
    user_session(monkeypatch, ["ingest.token:issue"])
    response = client.post(
        "/api/v1/admin/ingest-tokens",
        headers={"Authorization": "Bearer synthetic"},
        json={"expires_hours": 2},
    )
    assert response.status_code == 201, response.text
    assert response.headers["Cache-Control"] == "no-store"
    token = response.json()["token"]
    assert verify_token(token, "synthetic-signing-key", "dev")["issued_by"] == "synthetic-issuer"
    assert token not in str(audit.record.call_args)
    assert audit.record.call_args.kwargs["actor"].id == "synthetic-issuer"
    audit.record.return_value = None
    assert (
        client.post(
            "/api/v1/admin/ingest-tokens", headers={"Authorization": "Bearer synthetic"}, json={}
        ).status_code
        == 503
    )


@pytest.mark.parametrize(
    "payload",
    [{"expires_hours": 721}, {"expires_hours": 0}, {"environment": "prod"}, {"scope": "admin"}],
)
def test_issuer_cannot_override_server_scope(issuance, monkeypatch, payload):
    client, audit = issuance
    user_session(monkeypatch, ["ingest.token:issue"])
    assert (
        client.post(
            "/api/v1/admin/ingest-tokens",
            headers={"Authorization": "Bearer synthetic"},
            json=payload,
        ).status_code
        == 422
    )
    audit.record.assert_not_called()
