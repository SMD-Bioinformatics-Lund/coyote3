"""HTTP boundary tests for governed clinical reporting rule routes."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.interfaces.http.v1.admin import clinical_rules as rules
from coyote3.application.operations import ApplicationRuntime, ClinicalRules
from coyote3.application.reporting.clinical_rules.authoring import ClinicalRuleAuthoringService
from coyote3.contracts.schemas.clinical_rules import (
    ClinicalRuleDecision,
    ClinicalRuleDraftCreate,
    ClinicalRuleScope,
    ClinicalRuleTransition,
)
from tests.fixtures.api import mock_collections as fx
from tests.unit.reporting.test_clinical_rules import _document


def _operations(user, service):
    """Exercise the SDK boundary with explicit synthetic authorization capabilities."""
    policy = SimpleNamespace(
        permission_allowed=lambda *args, **kwargs: True,
        scope_allowed=lambda *args, **kwargs: True,
    )
    runtime = ApplicationRuntime(
        authenticate=lambda: user,
        policy_factory=lambda actor: policy,
        sample_loader=lambda identity: {"_id": identity},
        assay_loader=lambda identity: {"asp_group": "synthetic"},
        audit_access=lambda event: None,
    )
    return ClinicalRules(runtime, lambda: service, lambda: service)


def test_list_rule_sets_passes_filters_and_pagination(monkeypatch) -> None:
    monkeypatch.setattr(rules, "_serializable", lambda value: value)
    service = SimpleNamespace(
        list=lambda **kwargs: {"items": [], "total": 0, **kwargs},
    )

    result = rules.list_rule_sets(
        status="draft",
        q="hema",
        page=2,
        per_page=25,
        _user=fx.api_user(),
        service=_operations(fx.api_user(), service),
    )

    assert result == {
        "items": [],
        "total": 0,
        "status": "draft",
        "search": "hema",
        "page": 2,
        "per_page": 25,
    }


def test_authoring_options_are_loaded_from_the_service() -> None:
    expected = {
        "assays": [
            {
                "asp_id": "hema_gmsv1",
                "name": "Hematology",
                "display_name": "Hematology",
                "analyte": "dna",
            }
        ]
    }

    assert (
        rules.clinical_rule_authoring_options(
            _user=fx.api_user(),
            service=_operations(fx.api_user(), SimpleNamespace(authoring_options=lambda: expected)),
        )
        == expected
    )


def test_authoring_options_http_response_preserves_assay_short_name() -> None:
    """Real authoring-service choices serialize through the endpoint's strict response model."""
    service = ClinicalRuleAuthoringService(
        object(),
        assay_panel_repository=SimpleNamespace(
            get_all_asps=lambda **kwargs: [
                {
                    "asp_id": "synthetic_assay",
                    "name": "Synthetic assay",
                    "display_name": "Synthetic assay - extended description",
                    "asp_category": "dna",
                }
            ],
        ),
        assay_diagnosis_repository=SimpleNamespace(list_for_assay=lambda *args, **kwargs: []),
    )
    app = FastAPI()
    app.include_router(rules.router)
    route = next(
        route for route in rules.router.routes if route.path.endswith("/authoring-options")
    )
    for dependency in route.dependant.dependencies:
        if dependency.name == "_user":
            app.dependency_overrides[dependency.call] = fx.api_user
        elif dependency.name == "service":
            app.dependency_overrides[dependency.call] = lambda: _operations(fx.api_user(), service)
    with TestClient(app) as client:
        response = client.get("/api/v1/admin/clinical-rule-sets/authoring-options")
    assert response.status_code == 200
    cnv_terms = response.json()["sentence_terminology"]["sv"]["cnv_summary"]
    assert cnv_terms["effect_labels"] == {"gain": "amplifiering", "loss": "förlust"}
    assert response.json()["assays"] == [
        {
            "asp_id": "synthetic_assay",
            "name": "Synthetic assay",
            "display_name": "Synthetic assay - extended description",
            "analyte": "dna",
            "diagnoses": [{"diagnosis_id": "base", "display_name": "Base"}],
        }
    ]


@pytest.mark.parametrize("include_metadata", [False, True])
def test_export_http_omits_metadata_unless_requested(include_metadata):
    """The response contract must not inject audit defaults into portable exports."""
    source = _document(status="published", active=True)
    service = ClinicalRuleAuthoringService(
        SimpleNamespace(
            get=lambda _: source.model_dump(mode="python", by_alias=True),
        )
    )
    app = FastAPI()
    app.include_router(rules.router)
    route = next(route for route in rules.router.routes if route.path.endswith("/export"))
    for dependency in route.dependant.dependencies:
        if dependency.name == "_user":
            app.dependency_overrides[dependency.call] = fx.api_user
        elif dependency.name == "service":
            app.dependency_overrides[dependency.call] = lambda: _operations(fx.api_user(), service)
    query = "?include_metadata=true" if include_metadata else ""
    with TestClient(app) as client:
        response = client.get("/api/v1/admin/clinical-rule-sets/versions/source/export" + query)
    assert response.status_code == 200
    payload = response.json()
    assert payload["blocks"] == source.model_dump(mode="json", exclude={"id_"})["blocks"]
    assert ("created_by" in payload) is include_metadata
    assert ("content_version" in payload) is include_metadata
    assert ("revision" in payload) is include_metadata
    assert ("_id" in payload) is include_metadata
    if include_metadata:
        assert payload["status"] == "published" and payload["active"] is True
    else:
        assert "review" not in payload and "lifecycle" not in payload


@pytest.mark.parametrize("extra_field", [False, True])
def test_bulk_annotation_preview_http_uses_safe_facts_without_writes(extra_field):
    """Synthetic previews return rendered Markdown and reject sample-specific inputs."""
    from coyote3.contracts.schemas.clinical_rules import BulkAnnotationRule
    from tests.unit.reporting.test_clinical_rule_authoring_exhaustive import Repository

    document = _document(status="draft")
    document.bulk_annotation_rules = [
        BulkAnnotationRule(
            rule_id="gene_text",
            name="Gene text",
            tier=2,
            order=10,
            output=[
                {"type": "text", "value": "**Reviewed** "},
                {"type": "fact", "path": "finding.gene"},
            ],
        )
    ]
    repository = Repository(document)
    before = repository.document.copy()
    service = ClinicalRuleAuthoringService(repository)
    app = FastAPI()
    app.include_router(rules.router)
    route = next(
        route for route in rules.router.routes if route.path.endswith("/bulk-annotations/preview")
    )
    for dependency in route.dependant.dependencies:
        if dependency.name == "_user":
            app.dependency_overrides[dependency.call] = fx.api_user
        elif dependency.name == "service":
            app.dependency_overrides[dependency.call] = lambda: _operations(fx.api_user(), service)
    payload = {"tier": 2, "gene": "GENE_A"}
    if extra_field:
        payload["sample_name"] = "synthetic"
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/admin/clinical-rule-sets/versions/source/bulk-annotations/preview",
            json=payload,
        )
    assert response.status_code == (422 if extra_field else 200)
    if not extra_field:
        assert response.json() == {"rule_id": "gene_text", "text": "**Reviewed** GENE_A"}
    assert repository.document == before


@pytest.mark.parametrize("revision,status", [(1, 200), (99, 409), (None, 422)])
@pytest.mark.parametrize("state", ["submitted", "in_clinical_review", "approved"])
def test_reopen_http_requires_the_current_review_revision(revision, status, state):
    from api.app.main import app_error_handler
    from coyote3.domain.exceptions import AppError
    from tests.unit.reporting.test_clinical_rule_authoring_exhaustive import (
        Repository,
        governed_service,
    )

    repository = Repository(_document(status=state))
    service = governed_service(repository)
    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(rules.router)
    route = next(route for route in rules.router.routes if route.path.endswith("/reopen"))
    for dependency in route.dependant.dependencies:
        if dependency.name == "_user":
            app.dependency_overrides[dependency.call] = fx.api_user
        elif dependency.name == "service":
            app.dependency_overrides[dependency.call] = lambda: _operations(fx.api_user(), service)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/admin/clinical-rule-sets/drafts/version/reopen",
            json={} if revision is None else {"revision": revision},
        )
    assert response.status_code == status
    assert repository.document["status"] == ("draft" if status == 200 else state)
    if status == 200:
        assert response.json()["revision"] == 2
        assert not any(response.json()["review"].values())


def test_revision_routes_return_immutable_history(monkeypatch) -> None:
    monkeypatch.setattr(rules, "_serializable", lambda value: value)
    service = SimpleNamespace(
        revisions=lambda document_id: [{"rule_set_oid": document_id, "revision": 2}],
        revision=lambda document_id, revision: {
            "rule_set_oid": document_id,
            "revision": revision,
        },
    )

    assert rules.list_rule_set_revisions(
        "rule-version", _user=fx.api_user(), service=_operations(fx.api_user(), service)
    ) == {"items": [{"rule_set_oid": "rule-version", "revision": 2}]}
    assert rules.get_rule_set_revision(
        "rule-version", 2, _user=fx.api_user(), service=_operations(fx.api_user(), service)
    ) == {
        "rule_set_oid": "rule-version",
        "revision": 2,
    }


def test_sample_testing_routes_preserve_user_scope(monkeypatch) -> None:
    monkeypatch.setattr(rules, "_serializable", lambda value: value)
    observed = {}

    def search_samples(**kwargs):
        observed["search"] = kwargs
        return {"items": [], "page": 1, "per_page": 20, "total": 0}

    user = fx.api_user()
    user.roles = ["clinical_rule_author"]
    user.asp_ids = ["assay_1"]
    user.envs = ["production"]
    result = rules.search_clinical_rule_test_samples(
        "rule-version",
        q="sample",
        match_diagnosis=True,
        page=1,
        per_page=20,
        user=user,
        service=_operations(user, SimpleNamespace(search_samples=search_samples)),
    )

    assert result["total"] == 0
    assert observed["search"]["allowed_asp_ids"] == ["assay_1"]
    assert observed["search"]["allowed_environments"] == ["production"]


def test_sample_preview_loads_authorized_sample(monkeypatch) -> None:
    monkeypatch.setattr(rules, "_serializable", lambda value: value)
    observed = {}

    def preview(**kwargs):
        observed.update(kwargs)
        return {"persisted": False}

    result = rules.preview_clinical_rule_with_sample(
        "rule-version",
        "sample-id",
        user=fx.api_user(),
        service=_operations(fx.api_user(), SimpleNamespace(preview=preview)),
    )

    assert result == {"persisted": False}
    assert observed == {
        "document_id": "rule-version",
        "sample": {"_id": "sample-id"},
        "include_condition_trace": False,
    }


def test_create_draft_records_authenticated_actor(monkeypatch) -> None:
    monkeypatch.setattr(rules, "_serializable", lambda value: value)
    observed = {}

    def create(payload, *, actor):
        observed.update(payload=payload, actor=actor)
        return {"status": "draft"}

    payload = ClinicalRuleDraftCreate(
        scope=ClinicalRuleScope(
            asp_id="hema_gmsv1", diagnosis_id="base", analyte="dna", language="sv"
        ),
        name="Hematology report rules",
    )
    user = fx.api_user()
    user.username = "rule.author"
    result = rules.create_rule_set_draft(
        payload,
        user=user,
        service=_operations(user, SimpleNamespace(create_draft=create)),
    )

    assert result["status"] == "draft"
    assert observed == {"payload": payload, "actor": "rule.author"}


def test_delete_draft_delegates_authenticated_actor() -> None:
    observed = {}

    def delete(document_id, *, expected_revision, actor):
        observed.update(document_id=document_id, expected_revision=expected_revision, actor=actor)

    user = fx.api_user()
    user.username = "rule.author"
    assert (
        rules.delete_rule_set_draft(
            "507f1f77bcf86cd799439011",
            revision=3,
            user=user,
            service=_operations(user, SimpleNamespace(delete_draft=delete)),
        )
        is None
    )
    assert observed == {
        "document_id": "507f1f77bcf86cd799439011",
        "expected_revision": 3,
        "actor": "rule.author",
    }


def test_review_decision_passes_explicit_reason_and_actor(monkeypatch) -> None:
    monkeypatch.setattr(rules, "_serializable", lambda value: value)
    observed = {}

    def decide(document_id, payload, *, actor):
        observed.update(document_id=document_id, payload=payload, actor=actor)
        return {"status": "approved"}

    payload = ClinicalRuleDecision(approve=True, reason="Clinical wording verified")
    user = fx.api_user()
    user.username = "clinical.reviewer"
    result = rules.decide_rule_set_clinical_review(
        "507f1f77bcf86cd799439011",
        payload,
        user=user,
        service=_operations(user, SimpleNamespace(clinical_decision=decide)),
    )

    assert result["status"] == "approved"
    assert observed["payload"] == payload
    assert observed["actor"] == "clinical.reviewer"


def test_retirement_delegates_reason_to_lifecycle_service(monkeypatch) -> None:
    monkeypatch.setattr(rules, "_serializable", lambda value: value)
    observed = {}

    def retire(document_id, payload, *, actor):
        observed.update(document_id=document_id, payload=payload, actor=actor)
        return {"status": "retired"}

    payload = ClinicalRuleTransition(reason="Replaced by version 3")
    user = fx.api_user()
    user.username = "publisher"
    result = rules.retire_rule_set(
        "507f1f77bcf86cd799439011",
        payload,
        user=user,
        service=_operations(user, SimpleNamespace(retire=retire)),
    )

    assert result["status"] == "retired"
    assert observed["payload"].reason == "Replaced by version 3"
