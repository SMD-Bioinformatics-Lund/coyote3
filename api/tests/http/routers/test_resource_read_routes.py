"""The HTTP read interface validates input and uses the real authorization service."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from api_test_support.mock_collections import api_user
from coyote.application.operations.resource_reads import ResourceReads
from coyote.application.operations.runtime import ApplicationRuntime
from coyote.domain.exceptions import AppError
from coyote_api.app.deps.application import get_resource_reads
from coyote_api.interfaces.http.v1.operations.resource_reads import router
from coyote_api.security import access
from coyote_contracts.retrieval import ResourceReadPage
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient


@pytest.fixture
def boundary(monkeypatch):
    user = api_user()
    user.roles = []
    user.permissions = ["sample:view"]
    monkeypatch.setattr(access, "_decode_session_user", lambda request: user)
    monkeypatch.setattr(access, "_audit_access_event", lambda **kwargs: None)
    monkeypatch.setattr(access, "get_roles_repository", lambda: None)
    monkeypatch.setattr(access, "get_permissions_repository", lambda: None)
    policy = SimpleNamespace(
        permission_allowed=lambda candidate, permission, **options: (
            permission in candidate.permissions
        ),
        scope_allowed=lambda candidate, context=None: True,
    )
    monkeypatch.setattr(access, "build_access_policy", lambda **kwargs: policy)
    repository = Mock()
    repository.query.return_value = ResourceReadPage(items=[{"name": "synthetic"}], total=1)
    runtime = ApplicationRuntime(
        authenticate=lambda: user,
        policy_factory=lambda actor: policy,
        sample_loader=lambda identity: None,
        assay_loader=lambda identity: None,
        audit_access=lambda event: None,
    )
    app = FastAPI()
    app.include_router(router)

    @app.exception_handler(AppError)
    async def app_error(request, exc):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    app.dependency_overrides[get_resource_reads] = lambda: ResourceReads(
        runtime, lambda: repository
    )
    with TestClient(app) as client:
        yield client, user, repository


def test_projection_and_typed_predicates_reach_scoped_application(boundary):
    client, _, repository = boundary
    result = client.post(
        "/api/v1/resources/read/samples/query",
        json={
            "filters": {"reported": False, "asp_id": "synthetic"},
            "fields": ["name"],
        },
    )
    assert result.status_code == 200
    assert result.json()["items"] == [{"name": "synthetic"}]
    assert repository.query.call_args.args[1].filters["reported"].eq is False


@pytest.mark.parametrize(
    "payload",
    [
        {"filters": {"password": "secret"}},
        {"filters": {"reported": "false"}},
        {"filters": {"reported": {"$ne": True}}},
        {"fields": ["patient_id"]},
        {"per_page": 1000},
        {"page": True},
        {"raw_query": {}},
        {"related_filters": {"configuration": {"secret": "value"}}},
    ],
)
def test_invalid_read_inputs_are_422_before_persistence(boundary, payload):
    client, _, repository = boundary
    assert client.post("/api/v1/resources/read/samples/query", json=payload).status_code == 422
    repository.query.assert_not_called()


def test_permission_and_query_string_and_unknown_resource(boundary):
    client, user, repository = boundary
    user.permissions = []
    assert (
        client.post("/api/v1/resources/read/samples/query", json={"operation": "count"}).status_code
        == 403
    )
    user.permissions = ["sample:view"]
    assert (
        client.post("/api/v1/resources/read/samples/query?reported=false", json={}).status_code
        == 422
    )
    assert client.post("/api/v1/resources/read/users/query", json={}).status_code == 422
    repository.query.assert_not_called()


def test_relations_cannot_bypass_catalog_permission(boundary):
    client, _, repository = boundary
    assert (
        client.post(
            "/api/v1/resources/read/samples/query",
            json={
                "operation": "exists",
                "related_filters": {"configuration": {"is_active": True}},
            },
        ).status_code
        == 403
    )
    repository.query.assert_not_called()
