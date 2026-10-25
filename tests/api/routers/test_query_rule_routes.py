"""HTTP validation and permission boundaries for query-rule authoring."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.deps.application import get_query_rules
from api.infra.mongo.selection import compile_selection
from api.interfaces.http.v1.admin.query_rules import router
from api.security import access
from coyote3.application.operations import ApplicationRuntime, QueryRules
from tests.fixtures.api.mock_collections import api_user


@pytest.fixture
def boundary(monkeypatch):
    """Exercise real route permission dependencies with an isolated access policy."""
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
            permission_allowed=lambda candidate, permission, **options: (
                permission in candidate.permissions
            ),
        ),
    )
    service = Mock()
    service.list.return_value = {"items": []}
    service.options.return_value = {"groups": [], "assays": []}
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_query_rules] = lambda: service
    with TestClient(app) as client:
        yield client, user, service


@pytest.mark.parametrize(
    "method,path,permission",
    [
        ("GET", "", "view"),
        ("GET", "/options", "view"),
        ("POST", "/test-samples", "test"),
        ("POST", "/test-samples/example/preview", "test"),
        ("POST", "/preview", "view"),
        ("POST", "/test-condition", "view"),
        ("POST", "", "draft"),
        ("PUT", "/example", "draft"),
        ("POST", "/example/approve", "review"),
        ("POST", "/example/publish", "publish"),
        ("POST", "/example/retire", "retire"),
    ],
)
def test_every_route_requires_its_declared_permission(boundary, method, path, permission):
    client, user, service = boundary
    response = client.request(method, "/api/v1/admin/query-rule-sets" + path, json={})
    assert response.status_code == 403
    assert not service.method_calls
    user.permissions = ["query_rules:" + permission]
    response = client.request(method, "/api/v1/admin/query-rule-sets" + path, json={})
    assert response.status_code == (200 if method == "GET" else 422)


def test_invalid_draft_preview_returns_422_without_service_call(boundary):
    client, user, service = boundary
    user.permissions = ["query_rules:view"]
    response = client.post(
        "/api/v1/admin/query-rule-sets/preview",
        json={
            "scope": {"assay_group": "example", "analysis": "snv"},
            "content": {"exceptions": [{"id": "unsafe", "mode": "admit", "$where": "true"}]},
        },
    )
    assert response.status_code == 422
    assert not service.method_calls


def test_synthetic_condition_testing_uses_no_repository(boundary):
    from coyote3.application.query_rules.service import QueryRuleService

    client, user, service = boundary
    user.permissions = ["query_rules:view"]
    service.test_condition.side_effect = QueryRuleService(
        None, selection_renderer=compile_selection
    ).test_condition
    response = client.post(
        "/api/v1/admin/query-rule-sets/test-condition",
        json={
            "analysis": "cnv",
            "condition": {"type": "predicate", "field": "size", "operator": "gte", "value": 100},
            "documents": [{"size": 101}, {"size": 99}, {}],
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "matches": [True, False, False],
        "predicate": {"size": {"$gte": 100}},
    }
    assert [call[0] for call in service.method_calls] == ["test_condition"]


def test_condition_operator_injection_is_rejected_at_http_boundary(boundary):
    client, user, service = boundary
    user.permissions = ["query_rules:view"]
    response = client.post(
        "/api/v1/admin/query-rule-sets/test-condition",
        json={
            "analysis": "cnv",
            "condition": {
                "type": "predicate",
                "field": "ratio",
                "operator": "eq",
                "value": {"$where": "true"},
            },
            "documents": [{}],
        },
    )
    assert response.status_code == 422
    assert not service.method_calls


def test_sample_search_forwards_access_scope(boundary):
    client, user, service = boundary
    user.permissions = ["query_rules:test"]
    runtime = ApplicationRuntime(
        authenticate=lambda: user,
        policy_factory=lambda actor: SimpleNamespace(
            permission_allowed=lambda *args, **kwargs: True
        ),
        sample_loader=Mock(),
        assay_loader=Mock(),
        audit_access=Mock(),
    )
    client.app.dependency_overrides[get_query_rules] = lambda: QueryRules(
        runtime, lambda: service, lambda: service
    )
    service.search_samples.return_value = {"items": [], "total": 0, "page": 1, "per_page": 20}
    result = client.post(
        "/api/v1/admin/query-rule-sets/test-samples", json={"scope": {"analysis": "snv"}}
    )
    assert result.status_code == 200
    assert service.search_samples.call_args.kwargs["allowed_asp_ids"] == user.asp_ids
    assert service.search_samples.call_args.kwargs["allowed_environments"] == user.envs


def test_sample_preview_checks_access_before_running_comparison(boundary):
    from fastapi import HTTPException

    client, user, service = boundary
    user.permissions = ["query_rules:test"]

    def denied(*args):
        raise HTTPException(403, "Forbidden sample")

    runtime = ApplicationRuntime(
        authenticate=lambda: user,
        policy_factory=lambda actor: SimpleNamespace(
            permission_allowed=lambda *args, **kwargs: True
        ),
        sample_loader=denied,
        assay_loader=Mock(),
        audit_access=Mock(),
    )
    client.app.dependency_overrides[get_query_rules] = lambda: QueryRules(
        runtime, lambda: service, lambda: service
    )
    result = client.post(
        "/api/v1/admin/query-rule-sets/test-samples/blocked/preview",
        json={"scope": {"analysis": "snv"}, "content": {"exceptions": []}},
    )
    assert result.status_code == 403
    service.preview.assert_not_called()
