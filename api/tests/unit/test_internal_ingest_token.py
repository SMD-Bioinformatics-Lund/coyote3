"""Host-owned authentication and policy for machine sample ingestion."""

from types import SimpleNamespace

import pytest
from coyote.application.operations.ingest_permissions import enforce_sample_ingest_permission
from coyote_api.infra.security.ingest_policy import SampleIngestPolicy
from coyote_api.security import access
from fastapi import HTTPException
from starlette.requests import Request


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
    from coyote_api.security.ingest_tokens import issue_token

    token = issue_token("synthetic-internal-token", "development")
    req = request(None)
    req.scope["headers"] = [(b"x-coyote-ingest-token", token.encode())]
    dependency = access.require_sample_ingest_access(req)
    user = next(dependency)
    try:
        assert user.username.startswith("ingest-token-")
        assert not user.is_superuser
        enforce_sample_ingest_permission(
            SimpleNamespace(
                policy_factory=lambda actor: SampleIngestPolicy(access.InternalIngestPrincipal)
            ),
            user,
            {"asp_id": "synthetic", "environment": "production"},
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
        enforce_sample_ingest_permission(
            SimpleNamespace(
                policy_factory=lambda actor: SampleIngestPolicy(access.InternalIngestPrincipal)
            ),
            user,
            {"asp_id": "synthetic", "environment": "development"},
        )
        enforce_sample_ingest_permission(
            SimpleNamespace(
                policy_factory=lambda actor: SampleIngestPolicy(access.InternalIngestPrincipal)
            ),
            user,
            {"asp_id": "synthetic", "environment": "production"},
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
