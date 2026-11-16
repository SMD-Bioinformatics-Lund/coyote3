"""Managed credentials fail closed across lifecycle, scope and authentication boundaries."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import mongomock
import pytest
from api_test_support.ingest_tokens import user_session
from api_test_support.mongo_settings import mongo_runtime
from coyote.application.accounts.service_tokens import ServiceTokens
from coyote.application.operations import ApplicationRuntime, Credentials
from coyote.application.operations.ingest_audit import IngestionAuditAttempt
from coyote.contracts.service_tokens import PersonalTokenCreate, ServiceTokenCreate
from coyote.domain.exceptions import AppError
from coyote_api.app.deps.application import get_credentials, get_sample_ingestion
from coyote_api.infra.security.ingest_policy import SampleIngestPolicy
from coyote_api.interfaces.http.v1.admin.service_tokens import router
from coyote_api.security import access
from coyote_mongo.repositories.service_tokens import MongoServiceTokenRepository
from fastapi import Depends, FastAPI, HTTPException
from fastapi import Request as FastAPIRequest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.requests import Request


@pytest.mark.parametrize("editor", [None, "d19e2836-e862-42df-b32f-97cb05ad3366", "invalid"])
def test_session_ingestion_validates_and_forwards_editor_header(monkeypatch, editor):
    """Session ingestion preserves a real editor UUID without passing Header metadata to the SDK."""
    from coyote_api.app.deps import application

    opened = Mock(return_value=SimpleNamespace(ingest=object()))
    monkeypatch.setattr(application, "open_application", opened)
    monkeypatch.setattr(
        application, "get_request_api_session", lambda _: SimpleNamespace(token="synthetic-session")
    )
    app = FastAPI()

    @app.post("/ingest")
    def ingest(operations=Depends(get_sample_ingestion)):
        return {"bound": operations is opened.return_value.ingest}

    with TestClient(app) as client:
        response = client.post("/ingest", headers={"X-Edit-Session": editor} if editor else {})
    if editor == "invalid":
        assert response.status_code == 422
        opened.assert_not_called()
    else:
        assert response.status_code == 200
        assert response.json() == {"bound": True}
        assert opened.call_args.args == ("synthetic-session",)
        assert opened.call_args.kwargs["editor_id"] == editor


@pytest.fixture
def service():
    collection = mongomock.MongoClient().identity.service_tokens
    users = {"owner": {"username": "owner", "is_active": True}}
    return ServiceTokens(
        MongoServiceTokenRepository(collection),
        users=SimpleNamespace(
            user_with_id=users.get, list_active_users_for_notifications=lambda: list(users.values())
        ),
        assays=SimpleNamespace(
            get_all_asps=lambda **_: [{"asp_id": "assay_a", "display_name": "Assay A"}]
        ),
        audience="testing",
        audit=Mock(),
    )


def payload(**changes):
    """Select one real test-registry assay and one clinical environment."""
    return ServiceTokenCreate.model_validate(
        {
            "name": "Synthetic pipeline",
            "owner": "owner",
            "asp_ids": ["assay_a"],
            "environments": ["testing"],
            "operations": ["sample_bundle"],
            **changes,
        }
    )


def actor():
    """Return the administrator accountable for credential lifecycle actions."""
    return SimpleNamespace(username="issuer")


def request(token, *, path="/api/v1/internal/ingest/sample-bundle", headers=None):
    """Build a machine request without a browser session or cookie."""
    values = {"authorization": f"Bearer {token}", **(headers or {})}
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": [(key.encode(), value.encode()) for key, value in values.items()],
        }
    )


def test_authenticated_machine_has_exact_scope_and_rechecks_revocation(service, monkeypatch):
    issued = service.issue(payload(), actor=actor())
    monkeypatch.setattr(access, "get_service_tokens", lambda: service)
    verifier = access.require_sample_ingest_access(request(issued.token))
    user = next(verifier)
    verifier.close()
    assert user.username == "service-token-" + issued.metadata.token_id
    assert not user.is_superuser
    policy = SampleIngestPolicy(
        access.InternalIngestPrincipal, scoped_principal_type=access.ServiceTokenPrincipal
    )
    assert policy.permission_allowed(
        user, "sample:edit:own", context={"asp_id": "assay_a", "environment": "testing"}
    )
    for context in [
        {"asp_id": "other", "environment": "testing"},
        {"asp_id": "assay_a", "environment": "production"},
    ]:
        assert not policy.permission_allowed(user, "sample:edit:own", context=context)
    assert not policy.permission_allowed(user, "clinical_rules:publish")
    audit = Mock()
    IngestionAuditAttempt(audit, actor=user, source="api")
    assert audit.record.call_args.kwargs["metadata"]["service_token_id"] == issued.metadata.token_id
    assert audit.record.call_args.kwargs["metadata"]["service_token_owner"] == "owner"
    service.revoke(issued.metadata.token_id, actor=actor())
    with pytest.raises(HTTPException) as error:
        next(access.require_sample_ingest_access(request(issued.token)))
    assert error.value.status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/internal/ingest/sample-bundle/upload",
        "/api/v1/internal/ingest/sample-bundle/async",
        "/api/v1/internal/ingest/collection",
        "/api/v1/auth/session",
    ],
)
def test_credential_cannot_escape_selected_operations(service, monkeypatch, path):
    issued = service.issue(payload(), actor=actor())
    monkeypatch.setattr(access, "get_service_tokens", lambda: service)
    with pytest.raises(HTTPException) as error:
        next(access.require_sample_ingest_access(request(issued.token, path=path)))
    assert error.value.status_code == 403


def test_multiple_credentials_are_rejected(service, monkeypatch):
    issued = service.issue(payload(), actor=actor())
    monkeypatch.setattr(access, "get_service_tokens", lambda: service)
    with pytest.raises(HTTPException) as error:
        next(
            access.require_sample_ingest_access(
                request(issued.token, headers={"x-coyote-internal-token": "other"})
            )
        )
    assert error.value.status_code == 401


def test_upload_credentials_accept_deployment_prefixes_but_cannot_become_sessions(
    service, monkeypatch
):
    """The upload operation works under a proxy prefix and never creates a browser identity."""
    issued = service.issue(payload(operations=["sample_upload"]), actor=actor())
    monkeypatch.setattr(access, "get_service_tokens", lambda: service)
    req = request(issued.token, path="/coyote/api/v1/internal/ingest/sample-bundle/upload")
    req.scope["root_path"] = "/coyote"
    verifier = access.require_sample_ingest_access(req)
    assert next(verifier).service_token_id == issued.metadata.token_id
    verifier.close()
    monkeypatch.setattr(access, "_get_cached_api_session", lambda *_: None)
    with pytest.raises(HTTPException) as error:
        access._decode_session_user(request(issued.token, path="/api/v1/auth/session"))
    assert error.value.status_code == 401


def test_http_ingestion_runtime_enforces_scope_before_writes_and_reloads_revocation(
    service, monkeypatch
):
    """The actual HTTP/SDK composition cannot broaden a credential or retain revoked access."""
    from coyote_api.app import application_factory
    from coyote_api.app.deps import services as host_services

    issued = service.issue(payload(), actor=actor())
    monkeypatch.setattr(access, "get_service_tokens", lambda: service)
    backend = Mock()
    backend.ingest_sample_bundle.return_value = {
        "status": "ok",
        "sample_id": "synthetic-id",
        "sample_name": "synthetic",
    }
    monkeypatch.setattr(host_services, "get_internal_ingest_service", lambda: backend)
    monkeypatch.setattr(application_factory, "record_application_access", lambda *_args, **_: None)
    monkeypatch.setattr(
        application_factory, "ingest_submission_services", lambda: SimpleNamespace()
    )
    operations = get_sample_ingestion(request(issued.token))
    for sample in [
        {"name": "synthetic", "asp_id": "other", "environment": "testing"},
        {"name": "synthetic", "asp_id": "assay_a", "environment": "production"},
    ]:
        with pytest.raises(AppError) as error:
            operations.sample_bundle(sample)
        assert error.value.status_code == 403
    backend.ingest_sample_bundle.assert_not_called()
    sample = {"name": "synthetic", "asp_id": "assay_a", "environment": "testing"}
    operations.sample_bundle(sample)
    assert (
        backend.ingest_sample_bundle.call_args.kwargs["ingested_by"]
        == "service-token-" + issued.metadata.token_id
    )
    operations.authorize_sample(sample)
    backend.reset_mock()
    service.revoke(issued.metadata.token_id, actor=actor())
    with pytest.raises(HTTPException) as error:
        operations.sample_bundle(sample)
    assert error.value.status_code == 401
    backend.ingest_sample_bundle.assert_not_called()


def test_admin_http_creation_list_and_revocation_keep_secrets_private(service, monkeypatch):
    app = FastAPI()
    app.include_router(router)

    def credentials(request: FastAPIRequest):
        """Exercise the same revocable identity and policy checks used by SDK operations."""
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
        return Credentials(runtime, SimpleNamespace(service_tokens=lambda: service))

    app.dependency_overrides[get_credentials] = credentials
    monkeypatch.setattr(access, "_audit_access_event", lambda **_: None)
    monkeypatch.setattr(
        access,
        "get_permissions_repository",
        lambda: SimpleNamespace(
            get_all_permissions=lambda **_: [{"permission_id": "ingest.token:issue"}]
        ),
    )
    user_session(monkeypatch, ["ingest.token:issue"])

    @app.exception_handler(AppError)
    async def app_error(request, error):
        """Use the centralized application-error response shape in this isolated router test."""
        return JSONResponse(status_code=error.status_code, content=error.detail)

    with TestClient(app) as client:
        assert client.get("/api/v1/admin/service-tokens").status_code == 401
        headers = {"Authorization": "Bearer synthetic"}
        response = client.post(
            "/api/v1/admin/service-tokens", headers=headers, json=payload().model_dump()
        )
        assert response.status_code == 201, response.text
        assert response.headers["cache-control"] == "no-store"
        token = response.json()["token"]
        token_id = response.json()["metadata"]["token_id"]
        listed = client.get("/api/v1/admin/service-tokens", headers=headers)
        assert token not in listed.text and "token_hash" not in listed.text
        assert (
            client.delete(f"/api/v1/admin/service-tokens/{token_id}", headers=headers).status_code
            == 200
        )
        assert service.resolve(token) is None
        user_session(monkeypatch, [])
        assert (
            client.post(
                "/api/v1/admin/service-tokens", headers=headers, json=payload().model_dump()
            ).status_code
            == 403
        )


@pytest.fixture
def personal(service):
    """Use real current-role policy evaluation for a mutable ordinary user identity."""
    permissions = ["internal.ingest:manage", "sample:edit:own", "internal.task:view"]
    user = access.ApiUser(
        id="owner",
        username="owner",
        fullname="Owner",
        email="",
        roles=["operator"],
        role="operator",
        access_level=0,
        permissions=permissions.copy(),
        asp_ids=["assay_a"],
        assay_access=[{"asp_id": "assay_a", "environments": ["testing"]}],
        asp_groups=["demo"],
        envs=["testing"],
        asp_map={},
        auth_type=["local"],
    )
    roles = SimpleNamespace(
        get_all_roles=lambda: [
            {"role_id": "operator", "is_active": True, "permissions": permissions}
        ]
    )
    catalog = SimpleNamespace(
        get_all_permissions=lambda **_: [
            {"permission_id": value}
            for value in ["internal.ingest:manage", "sample:edit:own", "internal.task:view"]
        ]
    )

    def policy(actor):
        """Rebuild the current policy after every role/scope modification in these tests."""
        return access.build_access_policy(
            user=actor, roles_repository=roles, permissions_repository=catalog
        )

    service.user_loader = lambda username: user if username == "owner" else None
    service.permission_check = lambda actor, permission, context: (
        policy(actor).permission_allowed(actor, permission, context=context)
        if permission
        else policy(actor).scope_allowed(actor, context)
    )
    return service, user, permissions


def personal_payload(**changes):
    """Select account-bounded scopes without accepting an owner in the request."""
    data = payload(**changes).model_dump()
    data.pop("owner")
    return PersonalTokenCreate.model_validate(data)


def test_personal_tokens_cannot_choose_an_owner_or_exceed_current_access(personal):
    service, user, _permissions = personal
    with pytest.raises(ValidationError):
        PersonalTokenCreate.model_validate({**personal_payload().model_dump(), "owner": "another"})
    issued = service.issue_personal(personal_payload(), actor=user)
    assert issued.metadata.owner == user.username
    assert issued.metadata.kind == "personal"
    user.asp_ids = []
    user.assay_access = []
    with pytest.raises(AppError) as error:
        service.issue_personal(personal_payload(), actor=user)
    assert error.value.status_code == 403
    assert service.personal_options(actor=user).assays == []


def test_personal_list_and_revoke_never_include_other_owners_or_service_credentials(personal):
    service, user, _permissions = personal
    issued = service.issue_personal(personal_payload(), actor=user)
    managed = service.issue(payload(), actor=actor())
    assert [row.token_id for row in service.list_metadata(owner="owner", kind="personal")] == [
        issued.metadata.token_id
    ]
    assert service.list_metadata(owner="other", kind="personal") == []
    for token_id, acting in [
        (managed.metadata.token_id, user),
        (issued.metadata.token_id, SimpleNamespace(username="other")),
    ]:
        with pytest.raises(AppError) as error:
            service.revoke(token_id, actor=acting, personal_only=True)
        assert error.value.status_code == 404
    assert service.resolve(issued.token) is not None
    service.revoke(issued.metadata.token_id, actor=user, personal_only=True)
    assert service.resolve(issued.token) is None


def test_personal_requests_keep_user_identity_and_lose_removed_permissions(personal, monkeypatch):
    service, user, permissions = personal
    issued = service.issue_personal(personal_payload(), actor=user)
    monkeypatch.setattr(access, "get_service_tokens", lambda: service)
    verifier = access.require_sample_ingest_access(request(issued.token))
    principal = next(verifier)
    verifier.close()
    assert principal.username == user.username
    assert principal.service_token_id == issued.metadata.token_id
    assert not principal.is_superuser
    policy = SampleIngestPolicy(
        access.InternalIngestPrincipal, scoped_principal_type=access.ServiceTokenPrincipal
    )
    assert policy.permission_allowed(
        principal, "sample:edit:own", context={"asp_id": "assay_a", "environment": "testing"}
    )
    permissions.remove("sample:edit:own")
    assert not policy.permission_allowed(
        principal, "sample:edit:own", context={"asp_id": "assay_a", "environment": "testing"}
    )
    permissions.remove("internal.ingest:manage")
    with pytest.raises(HTTPException) as error:
        next(access.require_sample_ingest_access(request(issued.token)))
    assert error.value.status_code == 403


@pytest.mark.parametrize("kind", ["service", "personal"])
@pytest.mark.parametrize("failure", ["revoked", "expired", "owner_disabled", "scope", "operation"])
def test_worker_rechecks_credential_before_any_ingestion_write(
    personal, monkeypatch, kind, failure
):
    """Queued jobs never retain authority from a revoked or broadened credential snapshot."""
    from coyote_api.app import application_factory
    from coyote_api.app.deps import services as host_services

    service, user, _permissions = personal
    changes = {"operations": ["sample_bundle_async", "job_status"]}
    issued = (
        service.issue_personal(personal_payload(**changes), actor=user)
        if kind == "personal"
        else service.issue(payload(**changes), actor=actor())
    )
    sample = {"name": "synthetic", "asp_id": "assay_a", "environment": "testing"}
    job = {
        "kind": "sample_bundle",
        "source_payload": sample,
        "submitted_by": user.username
        if kind == "personal"
        else "service-token-" + issued.metadata.token_id,
        "credential_id": issued.metadata.token_id,
        "credential_owner": "owner",
        "credential_operation": "sample_bundle_async",
        "credential_scope": {"asp_id": "assay_a", "environment": "testing"},
        "update_existing": False,
        "increment": False,
    }
    if failure == "revoked":
        service.revoke(issued.metadata.token_id, actor=actor())
    elif failure == "expired":
        service.repository.collection.update_one(
            {}, {"$set": {"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)}}
        )
    elif failure == "owner_disabled":
        service.users.user_with_id("owner")["is_active"] = False
    elif failure == "scope":
        sample["asp_id"] = "other"
    else:
        job["credential_operation"] = "sample_upload_async"
    monkeypatch.setattr(host_services, "get_service_tokens", lambda: service)
    backend = Mock()
    executor = application_factory.ingest_job_executor(backend, audit_access=Mock())
    with pytest.raises(AppError):
        executor.execute(job, record_completion=Mock())
    backend.ingest_sample_bundle.assert_not_called()


def test_worker_rechecks_personal_permission_removal(personal):
    service, user, permissions = personal
    issued = service.issue_personal(
        personal_payload(operations=["sample_bundle_async"]), actor=user
    )
    job = {
        "kind": "sample_bundle",
        "submitted_by": "owner",
        "credential_id": issued.metadata.token_id,
        "credential_owner": "owner",
        "credential_operation": "sample_bundle_async",
        "source_payload": {"asp_id": "assay_a", "environment": "testing"},
        "credential_scope": {"asp_id": "assay_a", "environment": "testing"},
    }
    service.authorize_job(job)
    permissions.remove("sample:edit:own")
    with pytest.raises(AppError) as error:
        service.authorize_job(job)
    assert error.value.status_code == 403


@pytest.mark.parametrize("kind", ["service", "personal"])
def test_authorized_worker_preserves_submitter_and_transaction_completion(
    personal, monkeypatch, kind
):
    """Valid managed jobs reach the existing transaction owner with unchanged commit fencing."""
    from coyote_api.app import application_factory
    from coyote_api.app.deps import services as host_services

    service, user, _permissions = personal
    changes = {"operations": ["sample_bundle_async"]}
    issued = (
        service.issue_personal(personal_payload(**changes), actor=user)
        if kind == "personal"
        else service.issue(payload(**changes), actor=actor())
    )
    identity = "owner" if kind == "personal" else "service-token-" + issued.metadata.token_id
    sample = {"name": "synthetic", "asp_id": "assay_a", "environment": "testing"}
    job = {
        "kind": "sample_bundle",
        "source_payload": sample,
        "submitted_by": identity,
        "credential_id": issued.metadata.token_id,
        "credential_owner": "owner",
        "credential_operation": "sample_bundle_async",
        "credential_scope": {"asp_id": "assay_a", "environment": "testing"},
        "update_existing": False,
        "increment": False,
    }
    monkeypatch.setattr(host_services, "get_service_tokens", lambda: service)
    backend = Mock()
    backend.ingest_sample_bundle.return_value = {"status": "ok", "sample_id": "synthetic"}
    callback = Mock()
    result = application_factory.ingest_job_executor(backend, audit_access=Mock()).execute(
        job, record_completion=callback
    )
    assert result["sample_id"] == "synthetic"
    assert backend.ingest_sample_bundle.call_args.args == (sample,)
    assert backend.ingest_sample_bundle.call_args.kwargs["ingested_by"] == identity
    assert backend.ingest_sample_bundle.call_args.kwargs["record_completion"] is callback
    callback.assert_not_called()


def test_async_submission_and_completed_status_remain_owned_and_scoped(personal, monkeypatch):
    """Completed jobs retain a scope even after their source manifests have been cleared."""
    from coyote.application.operations.ingest import IngestSubmissionServices
    from coyote_api.app import application_factory
    from coyote_api.app.deps import services as host_services
    from coyote_mongo.repositories.ingest_jobs import IngestJobsRepository

    service, user, _permissions = personal
    issued = service.issue_personal(
        personal_payload(operations=["sample_bundle_async", "job_status"]), actor=user
    )
    jobs = IngestJobsRepository(
        SimpleNamespace(
            app=mongo_runtime(), ingest_jobs_collection=mongomock.MongoClient().test.jobs
        )
    )
    monkeypatch.setattr(access, "get_service_tokens", lambda: service)
    monkeypatch.setattr(host_services, "get_internal_ingest_service", Mock())
    monkeypatch.setattr(application_factory, "record_application_access", Mock())
    monkeypatch.setattr(
        application_factory,
        "ingest_submission_services",
        lambda: IngestSubmissionServices(
            jobs=lambda: jobs,
            publish=Mock(),
            queue="ingest",
            task_name=lambda kind: f"synthetic.{kind}",
        ),
    )
    operations = get_sample_ingestion(
        request(issued.token, path="/api/v1/internal/ingest/sample-bundle/async")
    )
    accepted = operations.enqueue_sample_bundle(
        {"name": "synthetic", "asp_id": "assay_a", "environment": "testing"}
    )
    job_id = accepted["task_id"]
    stored = jobs.get(job_id)
    assert stored["credential_id"] == issued.metadata.token_id
    assert stored["credential_owner"] == "owner"
    assert issued.token not in str(stored)
    req = request(issued.token, path="/api/v1/internal/tasks/" + job_id)
    req.scope["method"] = "GET"
    status = get_sample_ingestion(req)
    assert status.job_status(job_id)["state"] == "PENDING"
    second = service.issue_personal(personal_payload(operations=["job_status"]), actor=user)
    other_request = request(second.token, path="/api/v1/internal/tasks/" + job_id)
    other_request.scope["method"] = "GET"
    with pytest.raises(AppError) as error:
        get_sample_ingestion(other_request).job_status(job_id)
    assert error.value.status_code == 404
    jobs.get_collection().update_one(
        {"_id": job_id},
        {
            "$set": {
                "state": "succeeded",
                "source_payload": None,
                "result": {"sample_id": "synthetic"},
            }
        },
    )
    assert status.job_status(job_id)["state"] == "SUCCESS"
    user.asp_ids = []
    user.assay_access = []
    with pytest.raises(AppError) as error:
        status.job_status(job_id)
    assert error.value.status_code == 403


def test_personal_http_management_is_session_owned_and_does_not_need_admin_grants(
    personal, monkeypatch
):
    """An ordinary user manages only their own personal credentials through the SDK boundary."""
    from coyote_api.interfaces.http.v1.operations.personal_tokens import router as personal_router

    service, user, permissions = personal
    monkeypatch.setattr(access, "_get_cached_api_session", lambda *_: SimpleNamespace(user=user))
    monkeypatch.setattr(access, "_audit_access_event", Mock())
    app = FastAPI()
    app.include_router(personal_router)

    def credentials(req: FastAPIRequest):
        """Bind the current session identity without administrative token permissions."""
        runtime = ApplicationRuntime(
            authenticate=lambda: access._decode_session_user(req),
            policy_factory=Mock(),
            sample_loader=Mock(),
            assay_loader=Mock(),
            audit_access=Mock(),
        )
        return Credentials(runtime, SimpleNamespace(service_tokens=lambda: service))

    app.dependency_overrides[get_credentials] = credentials

    @app.exception_handler(AppError)
    async def app_error(req, error):
        """Serialize deliberate application denial without exposing other token records."""
        return JSONResponse(status_code=error.status_code, content=error.detail)

    headers = {"Authorization": "Bearer synthetic-session"}
    with TestClient(app) as client:
        assert client.get("/api/v1/auth/personal-tokens").status_code == 401
        response = client.post(
            "/api/v1/auth/personal-tokens", headers=headers, json=personal_payload().model_dump()
        )
        assert response.status_code == 201, response.text
        assert response.json()["metadata"]["kind"] == "personal"
        assert response.headers["cache-control"] == "no-store"
        metadata = response.json()["metadata"]
        secret = response.json()["token"]
        service.issue(payload(), actor=actor())
        listed = client.get("/api/v1/auth/personal-tokens", headers=headers)
        assert len(listed.json()["items"]) == 1
        assert secret not in listed.text and "token_hash" not in listed.text
        forged = client.post(
            "/api/v1/auth/personal-tokens",
            headers=headers,
            json={**personal_payload().model_dump(), "owner": "another"},
        )
        assert forged.status_code == 422
        permissions.clear()
        assert (
            client.post(
                "/api/v1/auth/personal-tokens",
                headers=headers,
                json=personal_payload().model_dump(),
            ).status_code
            == 403
        )
        assert (
            client.delete(
                "/api/v1/auth/personal-tokens/" + metadata["token_id"], headers=headers
            ).status_code
            == 200
        )
