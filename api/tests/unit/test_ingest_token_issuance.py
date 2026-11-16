"""Require user authorization and durable audit for credential issuance."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from api_test_support.ingest_tokens import user_session
from coyote.application.operations import ApplicationRuntime, Credentials
from coyote.domain.exceptions import AppError
from coyote_api.app.application_factory import issue_ingest_credential
from coyote_api.app.deps import services
from coyote_api.app.deps.application import get_credentials
from coyote_api.app.runtime_state import app as runtime_app
from coyote_api.config import security
from coyote_api.interfaces.http.v1.admin import operations
from coyote_api.security import access
from coyote_api.security.ingest_tokens import verify_token
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient


@pytest.fixture
def issuance(monkeypatch):
    audit = Mock()
    audit.record.return_value = "synthetic-audit-id"
    monkeypatch.setattr(security, "get_internal_api_token", lambda config: "synthetic-signing-key")
    monkeypatch.setattr(runtime_app, "config", {"ENV_NAME": "development"})
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
    monkeypatch.setattr(services, "get_audit_service", lambda: audit)

    def credentials(request: Request):
        user = access._decode_session_user(request)
        runtime = ApplicationRuntime(
            authenticate=lambda: user,
            policy_factory=lambda actor: access.build_access_policy(
                user=actor,
                roles_repository=access.get_roles_repository(),
                permissions_repository=access.get_permissions_repository(),
            ),
            sample_loader=Mock(),
            assay_loader=Mock(),
            audit_access=Mock(),
        )
        return Credentials(runtime, SimpleNamespace(issue_token=issue_ingest_credential))

    app.dependency_overrides[get_credentials] = credentials

    @app.exception_handler(AppError)
    async def app_error(request, error):
        return JSONResponse(status_code=error.status_code, content=error.detail)

    return TestClient(app), audit


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
