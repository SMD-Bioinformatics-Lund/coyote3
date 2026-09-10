"""Verify that unattended sample ingestion never grants general user administration."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from api.interfaces.http.operations import internal
from api.security import access


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


def request(token):
    headers = [] if token is None else [(b"x-coyote-internal-token", token.encode())]
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/internal/ingest/sample-bundle/upload",
            "headers": headers,
        }
    )


def test_expiring_machine_token_is_accepted_without_login(token_policy):
    from api.security.ingest_tokens import issue_token

    token = issue_token("synthetic-internal-token", "development")
    req = request(None)
    req.scope["headers"] = [(b"x-coyote-ingest-token", token.encode())]
    dependency = access.require_sample_ingest_access(req)
    user = next(dependency)
    try:
        assert user.username.startswith("ingest-token-")
        assert not user.is_superuser
        internal._enforce_sample_ingest_permission(
            user, {"asp_id": "synthetic", "environment": "production"}
        )
        with pytest.raises(HTTPException):
            access._enforce_access(user, permission="user:create")
    finally:
        dependency.close()


def test_machine_principal_is_scoped_without_user_account(token_policy):
    dependency = access.require_sample_ingest_access(request("synthetic-internal-token"))
    user = next(dependency)
    try:
        assert user.username == "internal-ingest"
        assert not user.is_superuser
        internal._enforce_sample_ingest_permission(
            user, {"asp_id": "synthetic", "environment": "development"}
        )
        internal._enforce_sample_ingest_permission(
            user, {"asp_id": "synthetic", "environment": "production"}
        )
        with pytest.raises(HTTPException):
            access._enforce_access(user, permission="user:create")
    finally:
        dependency.close()


@pytest.mark.parametrize("token", ["", "wrong-token"])
def test_invalid_machine_token_fails_closed(token_policy, token):
    with pytest.raises(HTTPException) as denied:
        next(access.require_sample_ingest_access(request(token)))
    assert denied.value.status_code == 403


def test_user_session_authentication_remains_supported(monkeypatch):
    user = object()

    def dependency(req):
        yield user

    monkeypatch.setattr(access, "require_access", lambda **kwargs: dependency)
    assert list(access.require_sample_ingest_access(request(None))) == [user]


def test_upload_accepts_internal_token_but_collection_routes_do_not(token_policy, monkeypatch):
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
    app.dependency_overrides[internal.get_internal_ingest_service] = lambda: service
    monkeypatch.setattr(
        internal,
        "_prepare_uploaded_bundle",
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
