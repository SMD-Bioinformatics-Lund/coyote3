"""HTTP boundary tests for governed clinical reporting rule routes."""

from __future__ import annotations

from types import SimpleNamespace

from api.contracts.schemas.clinical_rules import (
    ClinicalRuleDecision,
    ClinicalRuleDraftCreate,
    ClinicalRuleScope,
    ClinicalRuleTransition,
)
from api.interfaces.http.admin import clinical_rules as rules
from tests.fixtures.api import mock_collections as fx


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
        service=service,
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
        "assays": [{"asp_id": "hema_gmsv1", "display_name": "Hematology", "analyte": "dna"}]
    }

    assert (
        rules.clinical_rule_authoring_options(
            _user=fx.api_user(),
            service=SimpleNamespace(authoring_options=lambda: expected),
        )
        == expected
    )


def test_revision_routes_return_immutable_history(monkeypatch) -> None:
    monkeypatch.setattr(rules, "_serializable", lambda value: value)
    service = SimpleNamespace(
        revisions=lambda document_id: [{"rule_set_oid": document_id, "revision": 2}],
        revision=lambda document_id, revision: {
            "rule_set_oid": document_id,
            "revision": revision,
        },
    )

    assert rules.list_rule_set_revisions("rule-version", _user=fx.api_user(), service=service) == {
        "items": [{"rule_set_oid": "rule-version", "revision": 2}]
    }
    assert rules.get_rule_set_revision("rule-version", 2, _user=fx.api_user(), service=service) == {
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
        match_subpanel=True,
        page=1,
        per_page=20,
        user=user,
        service=SimpleNamespace(search_samples=search_samples),
    )

    assert result["total"] == 0
    assert observed["search"]["allowed_asp_ids"] == ["assay_1"]
    assert observed["search"]["allowed_environments"] == ["production"]


def test_sample_preview_loads_authorized_sample(monkeypatch) -> None:
    monkeypatch.setattr(rules, "_serializable", lambda value: value)
    monkeypatch.setattr(rules, "_get_sample_for_api", lambda sample_id, user: {"_id": sample_id})
    observed = {}

    def preview(**kwargs):
        observed.update(kwargs)
        return {"persisted": False}

    result = rules.preview_clinical_rule_with_sample(
        "rule-version",
        "sample-id",
        user=fx.api_user(),
        service=SimpleNamespace(preview=preview),
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
            asp_id="hema_gmsv1", subpanel_id="base", analyte="dna", language="sv"
        ),
        name="Hematology report rules",
    )
    user = fx.api_user()
    user.username = "rule.author"
    result = rules.create_rule_set_draft(
        payload,
        user=user,
        service=SimpleNamespace(create_draft=create),
    )

    assert result["status"] == "draft"
    assert observed == {"payload": payload, "actor": "rule.author"}


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
        service=SimpleNamespace(clinical_decision=decide),
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
        service=SimpleNamespace(retire=retire),
    )

    assert result["status"] == "retired"
    assert observed["payload"].reason == "Replaced by version 3"
