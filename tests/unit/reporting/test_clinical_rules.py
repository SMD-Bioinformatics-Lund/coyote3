"""Canonical clinical reporting rule engine and governance tests."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from bson import ObjectId

from coyote3.application.reporting.clinical_rules.authoring import ClinicalRuleAuthoringService
from coyote3.application.reporting.clinical_rules.evaluator import ClinicalRuleEvaluator
from coyote3.application.reporting.clinical_rules.preparation import prepare_report_context
from coyote3.application.reporting.clinical_rules.renderers import render_tier_summary
from coyote3.application.reporting.clinical_rules.service import (
    ClinicalRuleService,
    rendered_summary,
)
from coyote3.application.reporting.clinical_rules.validation import content_hash, validate_rule_set
from coyote3.contracts.schemas.clinical_rules import (
    ClinicalRule,
    ClinicalRuleBlock,
    ClinicalRuleDecision,
    ClinicalRuleDraftCreate,
    ClinicalRuleDraftUpdate,
    ClinicalRulePredicate,
    ClinicalRuleSetDoc,
    ClinicalRuleStatus,
    ClinicalRuleTestCase,
    ClinicalRuleTransition,
)
from coyote3.domain.exceptions import AppError


@pytest.mark.parametrize(
    "presentation,expected",
    [
        ("paragraph", ["First.", "Second.", "Third."]),
        ("continue", ["First. Second. Third."]),
        ("line", ["First.  \nSecond.  \nThird."]),
        ("bullet", ["- First.\n- Second.\n- Third."]),
        ("numbered", ["1. First.\n1. Second.\n1. Third."]),
    ],
)
def test_matched_rules_respect_explicit_paragraph_and_list_placement(presentation, expected):
    """Presentation changes layout after matching without changing condition decisions."""
    document = _document()
    document.blocks = [
        ClinicalRuleBlock(
            block_id="layout",
            name="Layout",
            section="Summary",
            section_order=1,
            block_order=1,
            show_heading=False,
            match_strategy="all_matches",
            rules=[
                ClinicalRule(
                    rule_id=f"sentence_{index}",
                    name=f"Sentence {index}",
                    order=index,
                    presentation=presentation,
                    output=[{"type": "text", "value": text}],
                )
                for index, text in enumerate(["First.", "Second.", "Third."])
            ],
        )
    ]
    document.content_hash = content_hash(document)
    result = ClinicalRuleEvaluator().evaluate(_context(), document, reporting_analyses={"SNV"})
    assert result.sections["Summary"] == expected
    assert len([item for item in result.trace if item.matched]) == 3


def test_default_presentation_preserves_existing_publication_hashes():
    """Adding the default layout field does not invalidate older released content."""
    document = _document()
    before = content_hash(document)
    for block in document.blocks:
        for rule in block.rules:
            rule.presentation = "paragraph"
            assert "presentation" not in rule.model_dump()
    assert content_hash(document) == before


def test_annotation_templates_are_scoped_published_and_integrity_checked():
    """Bulk text uses the published DNA scope without reading ASPC snapshots."""
    from coyote3.contracts.schemas.clinical_rules import BulkAnnotationRule

    doc = _document(status="published", active=True)
    doc.bulk_annotation_rules = [
        BulkAnnotationRule(
            rule_id="annotation",
            name="Annotation",
            tier=3,
            order=10,
            output=[{"type": "text", "value": "Reviewed annotation."}],
        )
    ]
    doc.content_hash = content_hash(doc)
    configuration = _configuration(doc)
    sample = {"asp_id": "assay_1", "asp_category": "dna", "diagnosis_id": "base"}
    service = ClinicalRuleService(
        SimpleNamespace(
            list_active_for_assay=lambda *args, **kwargs: [
                doc.model_dump(mode="python", by_alias=True)
            ]
        )
    )
    assert service.bulk_annotation_release(aspc=configuration, sample=sample) == doc
    doc.bulk_annotation_rules[0].name = "Changed"
    with pytest.raises(ValueError, match="integrity"):
        service.bulk_annotation_release(aspc=configuration, sample=sample)
    doc.content_hash = content_hash(doc)
    configuration["reporting"]["language"] = "en"
    assert service.bulk_annotation_release(aspc=configuration, sample=sample) is None


def test_annotation_templates_support_the_published_language():
    document = _document(status="published", active=True)
    document.scope.language = "en"
    document.rule_set_id = "assay_1__base__en"
    document.content_hash = content_hash(document)
    service = ClinicalRuleService(
        SimpleNamespace(
            list_active_for_assay=lambda *args, **kwargs: [document.model_dump(by_alias=True)]
        )
    )
    configuration = _configuration(document)
    configuration["reporting"]["language"] = "en"
    assert (
        service.bulk_annotation_release(
            aspc=configuration, sample={"asp_id": "assay_1", "asp_category": "dna"}
        )
        == document
    )


@pytest.mark.parametrize("tier", [0, 4, 7, "x"])
def test_bulk_annotation_templates_reject_unsupported_tiers(tier):
    with pytest.raises(ValueError):
        ClinicalRuleDraftUpdate(
            revision=1,
            bulk_annotation_rules=[
                {
                    "rule_id": "annotation",
                    "name": "Annotation",
                    "tier": tier,
                    "order": 10,
                    "output": [{"type": "text", "value": "Reviewed annotation."}],
                }
            ],
        )


def test_missing_published_rules_produce_no_automatic_summary():
    """An unconfigured rule scope permits a report without generated wording."""
    service = ClinicalRuleService(SimpleNamespace(list_active_for_assay=lambda *args, **kwargs: []))
    context = _context()
    evaluation = service.evaluate(aspc=context.aspc.model_dump(), context=context)
    assert evaluation is None
    assert rendered_summary(evaluation) == ""


def _context():
    return prepare_report_context(
        sample={
            "name": "SYNTHETIC_1",
            "asp_id": "assay_1",
            "diagnosis_id": "base",
            "environment": "testing",
        },
        asp={"asp_id": "assay_1", "asp_group": "demo", "accredited": True},
        aspc={
            "aspc_id": "assay_1_base_testing",
            "asp_id": "assay_1",
            "diagnosis_id": "base",
            "environment": "testing",
            "reporting": {
                "report_sections": ["SNV", "CNV"],
                "language": "sv",
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
                "diagnosis_id": "base",
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
            "test_cases": [
                {
                    "test_id": "tp53_positive",
                    "name": "Synthetic TP53 finding",
                    "facts": _context().model_dump(mode="json"),
                    "expected_rule_ids": ["tp53_exon", "positive"],
                    "expected_sections": {
                        "Findings": ["Finding in TP53."],
                        "Summary": ["Positive."],
                    },
                }
            ],
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


@pytest.mark.parametrize("analysis", ["HRD", "MSI", "TMB"])
def test_independent_measurement_rule_evaluation_and_section_gate(analysis):
    """Each measurement collection supports numeric rules and respects report selection."""
    payload = _document().model_dump(mode="python", by_alias=True)
    payload["analysis_declarations"] = {analysis: {"narrative": "enabled"}}
    payload["test_cases"] = []
    payload["blocks"] = [
        {
            "block_id": "measurement",
            "name": "Measurement",
            "analysis": analysis,
            "evaluation": {"mode": "each_item", "collection": analysis.lower()},
            "section": "Measurements",
            "section_order": 1,
            "block_order": 1,
            "match_strategy": "first_match",
            "rules": [
                {
                    "rule_id": "measured",
                    "name": "Measured",
                    "order": 1,
                    "condition": {
                        "type": "predicate",
                        "fact": "item.value",
                        "operator": "gte",
                        "value": 0,
                    },
                    "output": [{"type": "text", "value": "Measured."}],
                }
            ],
        }
    ]
    document = ClinicalRuleSetDoc.model_validate(payload)
    assert validate_rule_set(document).valid
    for unsupported in ("BIOMARKER", "LOH"):
        obsolete = document.model_copy(deep=True)
        obsolete.blocks[0].analysis = unsupported
        assert not validate_rule_set(obsolete).valid
    context = prepare_report_context(
        sample={"name": "synthetic", "asp_id": "assay_1"},
        asp={},
        aspc={"reporting": {"report_sections": [analysis]}},
        analyte="dna",
        applied_gene_lists=[],
        report_sections_data={
            "biomarkers": [
                {
                    "name": "synthetic",
                    "HRD": {"sum": 0, "tai": 0, "hrd": 0, "lst": 0},
                    "MSIS": {"tot": 100, "som": 0, "per": 0},
                    "TMB": {"value": 0, "unit": "mut/Mb"},
                }
            ]
        },
    )
    evaluator = ClinicalRuleEvaluator()
    assert evaluator.evaluate(context, document, reporting_analyses={analysis}).sections == {
        "Measurements": ["Measured."]
    }
    assert evaluator.evaluate(context, document, reporting_analyses=set()).sections == {}


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
    result = validate_rule_set(parsed, require_tests=True)
    assert result.valid is False
    assert "unexpected report text" in result.errors[0]


def _configuration(document, context=None):
    """Create a native pinned configuration from synthetic report facts and approved content."""
    context = context or _context()
    return {
        **context.aspc.model_dump(),
        "asp_category": document.scope.analyte,
        "clinical_rule_release": document.model_dump(mode="python", by_alias=True),
    }


def test_runtime_resolves_published_scope_and_verifies_hash():
    document = _document(status="published", active=True)

    class Repository:
        def list_active_for_assay(self, asp_id, **_scope):
            assert asp_id == "assay_1"
            return [document.model_dump(mode="python", by_alias=True)]

    result = ClinicalRuleService(Repository()).evaluate(
        aspc=_configuration(document), context=_context()
    )
    assert result.source.rule_set_id == "assay_1__base__sv"
    assert result.source.content_version == 1


def test_publication_changes_report_resolution_without_aspc_update_and_invalidates_preview():
    """A new publication changes report provenance even when rendered wording is identical."""
    from coyote3.application.operations.reporting import Reports
    from coyote3.application.reporting.preview_consistency import (
        preview_fingerprint,
        require_current_preview,
    )

    document = _document(status="published", active=True)
    configuration = _configuration(document)
    sample = _context().sample.model_dump()
    repository = SimpleNamespace(
        list_active_for_assay=lambda *args, **kwargs: [
            document.model_dump(mode="python", by_alias=True)
        ]
    )
    service = ClinicalRuleService(repository)

    def build(**kwargs):
        """Evaluate current rules using unchanged sample and configuration facts."""
        evaluation = service.evaluate(aspc=configuration, context=_context())
        return (
            "dna_report.html",
            {
                "sample": sample,
                "assay_config": configuration,
                "clinical_rule_evaluation": evaluation.model_dump(mode="json"),
            },
            [],
        )

    workflow = SimpleNamespace(
        validate_report_inputs=lambda *args: None, build_report_payload=build
    )
    reports = Reports(
        None,
        SimpleNamespace(
            configuration=lambda sample: configuration,
            workflow=lambda analyte: workflow,
            logger=None,
        ),
    )
    template, reviewed, _, _ = reports._build(sample, "dna", save=False, include_snapshot=False)
    fingerprint = preview_fingerprint(template, reviewed)
    receipt = deepcopy(reviewed["clinical_rule_resolution"])
    document.content_version = 2
    document.content_hash = content_hash(document)
    _, current, _, _ = reports._build(sample, "dna", save=True, include_snapshot=True)
    assert configuration["clinical_rule_release"]["content_version"] == 1
    assert current["clinical_rule_resolution"]["content_version"] == 2
    assert receipt["content_version"] == 1
    with pytest.raises(AppError, match="Refresh and review"):
        require_current_preview(fingerprint, template, current)


def test_clinical_profiles_resolve_live_and_are_recorded_in_report_sources():
    """Published profile sources refresh without becoming part of an ASPC revision."""
    from coyote3.application.reporting.clinical_rules.resolution import capture_clinical_rules
    from coyote3.application.resources.configuration_profiles import profile_hash

    document = _document(status="published", active=True)
    configuration = _configuration(document)
    profile = {
        "_id": "synthetic-profile",
        "profile_id": "scoped_rules",
        "kind": "clinical_rules",
        "version": 1,
        "bindings": [{"asp_group": "solid"}],
        "content": {"disable_blocks": []},
    }
    profile["content_hash"] = profile_hash(profile)
    service = ClinicalRuleService(
        SimpleNamespace(
            list_active_for_assay=lambda *args, **kwargs: [document.model_dump(by_alias=True)]
        ),
        profiles=SimpleNamespace(published=lambda: [deepcopy(profile)]),
        assays=SimpleNamespace(
            get_asp=lambda key: {
                "asp_id": key,
                "asp_group": "solid",
                "asp_category": "dna",
                "asp_family": "panel-dna",
            }
        ),
    )
    with capture_clinical_rules() as first:
        service.evaluate(aspc=configuration, context=_context())
    profile["version"] = 2
    with capture_clinical_rules() as second:
        service.evaluate(aspc=configuration, context=_context())
    assert first[document.rule_set_id]["profiles"][0]["version"] == 1
    assert second[document.rule_set_id]["profiles"][0]["version"] == 2
    assert "profile_sources" not in configuration


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

    def transition(self, _document_id, *, expected_revision, from_statuses, changes, event):
        if (
            self.document["status"] not in from_statuses
            or self.document["revision"] != expected_revision
        ):
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

    def publish(self, document_id, *, expected_revision, changes, event):
        return self.transition(
            document_id,
            expected_revision=expected_revision,
            from_statuses={"approved"},
            changes=changes,
            event=event,
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
    service = ClinicalRuleAuthoringService(
        repository,
        user_repository=users,
        role_repository=roles,
        assay_panel_repository=SimpleNamespace(
            get_all_asps=lambda **_: [{"asp_id": "assay_1", "asp_group": "demo"}],
            group_options=lambda: ["demo"],
        ),
    )
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
    service = ClinicalRuleAuthoringService(
        repository,
        assay_panel_repository=panels,
        assay_diagnosis_repository=SimpleNamespace(
            list_for_assay=lambda *_a, **_k: [{"diagnosis_id": "base", "display_name": "Base"}]
        ),
    )

    options = service.authoring_options()
    assert options["assays"] == [
        {
            "asp_id": "dna_a",
            "display_name": "DNA A",
            "name": "DNA A",
            "analyte": "dna",
            "diagnoses": [{"diagnosis_id": "base", "display_name": "Base"}],
        },
        {
            "asp_id": "rna_b",
            "display_name": "RNA B",
            "name": "RNA B",
            "analyte": "rna",
            "diagnoses": [{"diagnosis_id": "base", "display_name": "Base"}],
        },
    ]
    assert options["condition_values"]["sample.asp_id"] == ["rna_b", "dna_a"]
    assert options["condition_values"]["sample.diagnosis_id"] == ["base"]
    assert options["clinical_reviewers"] == []
    assert options["publishers"] == []
    assert (
        options["sentence_terminology"]["sv"]["tier_summary"]["single_gene_always_read_context"]
        is True
    )
    assert ClinicalRuleAuthoringService(object()).authoring_options() == {
        "assays": [],
        "condition_values": {},
        "clinical_reviewers": [],
        "publishers": [],
        "sentence_terminology": options["sentence_terminology"],
        "bulk_annotation_fact_paths": options["bulk_annotation_fact_paths"],
    }


def test_optional_swedish_sentence_wording_matches_grouped_default_branch_output():
    """Explicit insertion reproduces grouped prose without modifying shared defaults."""
    from coyote3.domain.common.reporting import STANDARD_TIER_SUMMARY_PHRASES

    options = ClinicalRuleAuthoringService(object()).authoring_options()
    terms = options["sentence_terminology"]["sv"]
    groups = [
        {
            "tier": 1,
            "finding_count": 1,
            "genes": [{"gene": "BCOR", "vaf_percentages": ["2%"]}],
        },
        {
            "tier": 2,
            "finding_count": 2,
            "genes": [
                {"gene": "SUZ12", "vaf_percentages": ["18%"]},
                {"gene": "CUX1", "vaf_percentages": ["4%"]},
            ],
        },
        {
            "tier": 3,
            "finding_count": 1,
            "genes": [{"gene": "ROBO2", "vaf_percentages": ["16%"]}],
        },
    ]
    assert render_tier_summary(groups, terms).strip() == (
        "Vid analysen finner man en mutation av stark klinisk signifikans (Tier I) "
        "i BCOR (i 2% av läsningarna). Vidare ses två mutationer av potentiell "
        "klinisk signifikans (Tier II): en i SUZ12 (18%) och en i CUX1 (4%). "
        "Slutligen ses en mutation av oklar klinisk signifikans (Tier III) "
        "i ROBO2 (i 16% av läsningarna)."
    )
    terms["tier_summary"]["first_prefix"] = "Changed draft wording"
    assert STANDARD_TIER_SUMMARY_PHRASES["first_prefix"] == "Vid analysen finner man "
    assert (
        ClinicalRuleAuthoringService(object()).authoring_options()["sentence_terminology"]["sv"][
            "tier_summary"
        ]["first_prefix"]
        == "Vid analysen finner man "
    )


@pytest.mark.parametrize(
    ("panel", "message"),
    [
        ({"asp_id": "assay_1", "asp_category": "dna", "is_active": False}, "active assay"),
        ({"asp_id": "assay_1", "asp_category": "rna", "is_active": True}, "analyte"),
    ],
)
def test_new_rule_scope_must_match_an_active_assay(panel, message):
    panels = SimpleNamespace(get_asp=lambda _asp_id: panel)
    service = ClinicalRuleAuthoringService(
        object(),
        assay_panel_repository=panels,
        assay_diagnosis_repository=SimpleNamespace(
            list_for_assay=lambda *_a, **_k: [{"diagnosis_id": "base", "display_name": "Base"}]
        ),
    )
    payload = ClinicalRuleDraftCreate(
        scope={"asp_id": "assay_1", "diagnosis_id": "base", "analyte": "dna"},
        name="Rules",
    )

    with pytest.raises(AppError, match=message):
        service.create_draft(payload, actor="author")
