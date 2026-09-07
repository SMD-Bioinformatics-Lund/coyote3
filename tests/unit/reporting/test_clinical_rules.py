"""Canonical clinical reporting rule engine and governance tests."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from bson import ObjectId

from api.application.reporting.clinical_rules.authoring import ClinicalRuleAuthoringService
from api.application.reporting.clinical_rules.evaluator import ClinicalRuleEvaluator
from api.application.reporting.clinical_rules.preparation import prepare_report_context
from api.application.reporting.clinical_rules.service import ClinicalRuleService
from api.application.reporting.clinical_rules.validation import content_hash, validate_rule_set
from api.contracts.schemas.clinical_rules import (
    ClinicalRuleDecision,
    ClinicalRuleDraftCreate,
    ClinicalRuleDraftUpdate,
    ClinicalRulePredicate,
    ClinicalRuleSetDoc,
    ClinicalRuleStatus,
    ClinicalRuleTestCase,
    ClinicalRuleTransition,
)
from api.domain.core.exceptions import AppError


def _context():
    return prepare_report_context(
        sample={
            "name": "SYNTHETIC_1",
            "asp_id": "assay_1",
            "subpanel_id": "base",
            "environment": "testing",
        },
        asp={"asp_id": "assay_1", "asp_group": "demo", "accredited": True},
        aspc={
            "aspc_id": "assay_1_base_testing",
            "asp_id": "assay_1",
            "subpanel_id": "base",
            "environment": "testing",
            "reporting": {
                "report_sections": ["SNV", "CNV"],
                "clinical_rule_set_id": "assay_1__base__sv",
            },
        },
        analyte="dna",
        applied_gene_lists=[],
        report_sections_data={
            "snvs": [
                {
                    "INFO": {
                        "selected_CSQ": {
                            "SYMBOL": "TP53",
                            "EXON": "7/11",
                            "HGVSp": "p.Arg248Gln",
                        }
                    },
                    "GT": [{"type": "case", "AF": 0.22}],
                    "classification": {"class": 1},
                }
            ]
        },
    )


def _document(*, status: str = "draft", active: bool = False) -> ClinicalRuleSetDoc:
    now = datetime.now(timezone.utc)
    published = status == "published"
    document = ClinicalRuleSetDoc.model_validate(
        {
            "_id": ObjectId(),
            "rule_set_id": "assay_1__base__sv",
            "content_version": 1,
            "revision": 1,
            "scope": {
                "asp_id": "assay_1",
                "subpanel_id": "base",
                "analyte": "dna",
                "language": "sv",
            },
            "name": "Synthetic clinical rules",
            "status": status,
            "active": active,
            "analysis_declarations": {
                "SNV": {"narrative": "enabled"},
                "CNV": {"narrative": "none"},
            },
            "blocks": [
                {
                    "block_id": "finding_context",
                    "name": "Finding context",
                    "analysis": "SNV",
                    "evaluation": {"mode": "each_finding"},
                    "section": "Findings",
                    "section_order": 100,
                    "block_order": 10,
                    "show_heading": True,
                    "match_strategy": "first_match",
                    "rules": [
                        {
                            "rule_id": "tp53_exon",
                            "name": "TP53 exon finding",
                            "order": 10,
                            "condition": {
                                "type": "all",
                                "children": [
                                    {
                                        "type": "predicate",
                                        "fact": "finding.gene",
                                        "operator": "eq",
                                        "value": "TP53",
                                    },
                                    {
                                        "type": "any",
                                        "children": [
                                            {
                                                "type": "predicate",
                                                "fact": "finding.exon",
                                                "operator": "overlaps",
                                                "value": ["7", "8"],
                                            },
                                            {
                                                "type": "predicate",
                                                "fact": "finding.hgvsp",
                                                "operator": "eq",
                                                "value": "p.Arg273His",
                                            },
                                        ],
                                    },
                                ],
                            },
                            "output": [
                                {"type": "text", "value": "Finding in "},
                                {
                                    "type": "fact",
                                    "path": "finding.gene",
                                    "formatter": "gene_symbol",
                                },
                                {"type": "text", "value": "."},
                            ],
                        }
                    ],
                },
                {
                    "block_id": "result_state",
                    "name": "Result state",
                    "analysis": "SNV",
                    "evaluation": {"mode": "once"},
                    "section": "Summary",
                    "section_order": 200,
                    "block_order": 10,
                    "show_heading": False,
                    "match_strategy": "exactly_one",
                    "rules": [
                        {
                            "rule_id": "positive",
                            "name": "Positive result",
                            "order": 10,
                            "condition": {
                                "type": "collection_match",
                                "collection": "findings",
                                "quantifier": "any",
                                "where": {
                                    "type": "predicate",
                                    "fact": "item.tier",
                                    "operator": "in",
                                    "value": [1, 2, 3],
                                },
                            },
                            "output": [{"type": "text", "value": "Positive."}],
                        },
                        {
                            "rule_id": "negative",
                            "name": "Negative result",
                            "order": 20,
                            "condition": {
                                "type": "collection_match",
                                "collection": "findings",
                                "quantifier": "none",
                                "where": {
                                    "type": "predicate",
                                    "fact": "item.tier",
                                    "operator": "in",
                                    "value": [1, 2, 3],
                                },
                            },
                            "output": [{"type": "text", "value": "Negative."}],
                        },
                    ],
                },
            ],
            "test_cases": [],
            "created_at": now,
            "created_by": "author",
            "updated_at": now,
            "updated_by": "author",
            "published_at": now if published else None,
            "published_by": "publisher" if published else None,
            "effective_from": now if published else None,
        }
    )
    document.content_hash = content_hash(document)
    return document


def test_nested_conditions_collection_quantifiers_and_output_nodes():
    result = ClinicalRuleEvaluator().evaluate(
        _context(), _document(), reporting_analyses={"SNV", "CNV"}
    )
    assert result.sections == {"Findings": ["Finding in TP53."], "Summary": ["Positive."]}
    assert {item.rule_id for item in result.trace if item.matched} == {"tp53_exon", "positive"}


def test_missing_facts_fail_closed_without_becoming_zero_or_false():
    document = _document()
    document.blocks[0].rules[0].condition = ClinicalRulePredicate(
        fact="finding.control_vaf_percent", operator="eq", value=0
    )
    reparsed = ClinicalRuleSetDoc.model_validate(document.model_dump(mode="python", by_alias=True))
    result = ClinicalRuleEvaluator().evaluate(
        _context(), reparsed, reporting_analyses={"SNV", "CNV"}
    )
    trace = next(item for item in result.trace if item.rule_id == "tp53_exon")
    assert trace.matched is False
    assert trace.missing_facts == []  # Prepared unknown is explicit None, not a missing path.


def test_validation_rejects_operator_incompatible_with_fact_type():
    document = _document()
    document.blocks[0].rules[0].condition = ClinicalRulePredicate(
        fact="finding.gene", operator="gt", value="TP53"
    )
    result = validate_rule_set(
        ClinicalRuleSetDoc.model_validate(document.model_dump(mode="python", by_alias=True))
    )
    assert result.valid is False
    assert "invalid for fact 'finding.gene'" in result.errors[0]


def test_validation_executes_embedded_exact_output_cases():
    document = _document()
    document.test_cases = [
        ClinicalRuleTestCase.model_validate(
            {
                "test_id": "positive_tp53",
                "name": "Reportable TP53 finding",
                "facts": _context().model_dump(mode="python"),
                "expected_rule_ids": ["tp53_exon", "positive"],
                "expected_sections": {
                    "Findings": ["Finding in TP53."],
                    "Summary": ["Positive."],
                },
            }
        )
    ]
    parsed = ClinicalRuleSetDoc.model_validate(document.model_dump(mode="python", by_alias=True))
    assert validate_rule_set(parsed).valid is True

    parsed.test_cases[0].expected_sections["Summary"] = ["Wrong text."]
    result = validate_rule_set(parsed)
    assert result.valid is False
    assert "unexpected report text" in result.errors[0]


def test_runtime_resolves_only_explicit_active_binding_and_verifies_hash():
    document = _document(status="published", active=True)

    class Repository:
        def get_active(self, rule_set_id):
            assert rule_set_id == "assay_1__base__sv"
            return document.model_dump(mode="python", by_alias=True)

    result = ClinicalRuleService(Repository()).evaluate(aspc={}, context=_context())
    assert result.source.rule_set_id == "assay_1__base__sv"
    assert result.source.content_version == 1


class _MemoryRepository:
    def __init__(self, document: ClinicalRuleSetDoc):
        self.document = document.model_dump(mode="python", by_alias=True)

    def get(self, _document_id):
        return deepcopy(self.document)

    def update_draft(self, _document_id, *, expected_revision, changes, actor):
        self.update_actor = actor
        if self.document["revision"] != expected_revision or self.document["status"] != "draft":
            return None
        self.document.update(changes)
        self.document["revision"] += 1
        return deepcopy(self.document)

    def transition(self, _document_id, *, from_statuses, changes, event):
        if self.document["status"] not in from_statuses:
            return None
        for key, value in changes.items():
            if "." in key:
                parent, child = key.split(".", 1)
                self.document.setdefault(parent, {})[child] = value
            else:
                self.document[key] = value
        self.document["revision"] += 1
        self.document.setdefault("lifecycle", []).append(event)
        return deepcopy(self.document)

    def publish(self, document_id, *, changes, event):
        return self.transition(
            document_id, from_statuses={"approved"}, changes=changes, event=event
        )


def test_draft_updates_use_optimistic_revision_locking():
    repository = _MemoryRepository(_document())
    service = ClinicalRuleAuthoringService(repository)
    updated = service.update_draft(
        str(repository.document["_id"]),
        ClinicalRuleDraftUpdate(revision=1, change_summary="Reviewed wording"),
        actor="author",
    )
    assert updated["revision"] == 2
    with pytest.raises(AppError, match="changed while it was being edited"):
        service.update_draft(
            str(repository.document["_id"]),
            ClinicalRuleDraftUpdate(revision=1, change_summary="Stale edit"),
            actor="author",
        )


def test_latest_editor_cannot_approve_own_rule_content():
    document = _document().model_copy(update={"status": ClinicalRuleStatus.IN_CLINICAL_REVIEW})
    repository = _MemoryRepository(document)
    service = ClinicalRuleAuthoringService(repository)
    with pytest.raises(AppError, match="latest content editor"):
        service.clinical_decision(
            str(repository.document["_id"]),
            ClinicalRuleDecision(approve=True, reason="Clinical review complete"),
            actor="author",
        )


def test_independent_review_and_publication_preserve_content_hash():
    document = _document().model_copy(update={"status": ClinicalRuleStatus.IN_CLINICAL_REVIEW})
    document.review.clinical_reviewer = "reviewer"
    repository = _MemoryRepository(document)
    roles = SimpleNamespace(
        get_all_roles_plus_permissions=lambda: [
            {"role_id": "clinical_rule_publisher", "permissions": ["clinical_rules:publish"]}
        ]
    )
    users = SimpleNamespace(
        list_active_users_for_notifications=lambda *, role_ids: (
            [{"username": "publisher", "fullname": "Publisher"}]
            if "clinical_rule_publisher" in role_ids
            else []
        )
    )
    service = ClinicalRuleAuthoringService(repository, user_repository=users, role_repository=roles)
    approved = service.clinical_decision(
        str(repository.document["_id"]),
        ClinicalRuleDecision(
            approve=True, reason="Clinical review complete", publisher="publisher"
        ),
        actor="reviewer",
    )
    assert approved["status"] == "approved"
    published = service.publish(
        str(repository.document["_id"]), ClinicalRuleTransition(), actor="publisher"
    )
    assert published["status"] == "published"
    assert published["active"] is True
    assert published["content_hash"] == content_hash(
        ClinicalRuleSetDoc.model_validate(repository.document)
    )


def test_new_rule_scope_requires_scope_and_name():
    service = ClinicalRuleAuthoringService(object())
    with pytest.raises(AppError, match="requires scope and name"):
        service.create_draft(ClinicalRuleDraftCreate(), actor="author")


def test_authoring_options_are_active_assay_backed_and_sorted():
    panels = SimpleNamespace(
        get_all_asps=lambda is_active: [
            {"asp_id": "rna_b", "display_name": "RNA B", "asp_category": "RNA"},
            {"asp_id": "dna_a", "display_name": "DNA A", "asp_category": "DNA"},
            {"asp_id": "bad", "display_name": "Unsupported", "asp_category": "protein"},
            {"display_name": "Missing ID", "asp_category": "DNA"},
        ]
    )
    repository = SimpleNamespace(list_rule_sets=lambda **_kwargs: ([], 0))
    service = ClinicalRuleAuthoringService(repository, assay_panel_repository=panels)

    options = service.authoring_options()
    assert options["assays"] == [
        {"asp_id": "dna_a", "display_name": "DNA A", "analyte": "dna"},
        {"asp_id": "rna_b", "display_name": "RNA B", "analyte": "rna"},
    ]
    assert options["condition_values"]["sample.asp_id"] == ["rna_b", "dna_a"]
    assert options["condition_values"]["sample.subpanel_id"] == ["base"]
    assert options["clinical_reviewers"] == []
    assert options["publishers"] == []
    assert ClinicalRuleAuthoringService(object()).authoring_options() == {
        "assays": [],
        "condition_values": {},
        "clinical_reviewers": [],
        "publishers": [],
    }


@pytest.mark.parametrize(
    ("panel", "message"),
    [
        (None, "require an active assay panel"),
        ({"asp_id": "assay_1", "asp_category": "dna", "is_active": False}, "active assay"),
        ({"asp_id": "assay_1", "asp_category": "rna", "is_active": True}, "analyte"),
    ],
)
def test_new_rule_scope_must_match_an_active_assay(panel, message):
    panels = SimpleNamespace(get_asp=lambda _asp_id: panel)
    service = ClinicalRuleAuthoringService(object(), assay_panel_repository=panels)
    payload = ClinicalRuleDraftCreate(
        scope={"asp_id": "assay_1", "subpanel_id": "base", "analyte": "dna"},
        name="Rules",
    )

    with pytest.raises(AppError, match=message):
        service.create_draft(payload, actor="author")
