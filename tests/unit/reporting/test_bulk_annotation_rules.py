"""Clinical regressions for bulk annotation templates, separate from report narration."""

from types import SimpleNamespace

import pytest

from coyote3.application.classification.bulk_annotation_rules import (
    bulk_annotation_group_options,
    render_bulk_annotation,
)
from coyote3.application.reporting.clinical_rules.evaluator import ClinicalRuleEvaluator
from coyote3.application.reporting.clinical_rules.validation import content_hash, validate_rule_set
from coyote3.contracts.schemas.clinical_rules import (
    BulkAnnotationPreviewRequest,
    BulkAnnotationRule,
    ClinicalRuleSetDoc,
)
from tests.unit.reporting.test_clinical_rules import _context, _document


def _rule(**changes):
    """Create a synthetic gene-conditioned annotation template."""
    return BulkAnnotationRule.model_validate(
        {
            "rule_id": "gene_text",
            "name": "Reviewed gene text",
            "tier": 2,
            "order": 10,
            "condition": {
                "type": "predicate",
                "fact": "finding.gene",
                "operator": "in",
                "value": ["GENE_A", "GENE_B"],
            },
            "output": [
                {"type": "text", "value": "**Reviewed** "},
                {"type": "fact", "path": "finding.gene"},
            ],
            **changes,
        }
    )


def _groups():
    """Return a synthetic hierarchy with an unrelated branch and a retired ancestor."""
    return [
        {"group_id": "leaf", "display_name": "Leaf", "parent_group_id": "parent"},
        {
            "group_id": "parent",
            "display_name": "Parent",
            "parent_group_id": "root",
            "is_active": False,
        },
        {"group_id": "root", "display_name": "Root"},
        {"group_id": "other", "display_name": "Other", "parent_group_id": "root"},
    ]


def test_hierarchy_conditions_and_dynamic_values_include_all_ancestors():
    document = _document()
    document.bulk_annotation_rules = [
        _rule(
            condition={
                "type": "predicate",
                "fact": "asp.group_path_ids",
                "operator": "contains",
                "value": "parent",
            },
            output=[
                {"type": "fact", "path": "asp.group_name"},
                {"type": "text", "value": " / "},
                {"type": "fact", "path": "asp.parent_group_name"},
                {"type": "text", "value": " / "},
                {"type": "list", "path": "asp.ancestor_group_ids", "conjunction": "and"},
                {"type": "text", "value": " / "},
                {"type": "fact", "path": "asp.root_group_name"},
            ],
        )
    ]
    assert validate_rule_set(document).valid
    groups = bulk_annotation_group_options(_groups())
    result = render_bulk_annotation(
        document, BulkAnnotationPreviewRequest(tier=2, asp_group="leaf"), groups=groups
    )
    assert result.text == "Leaf / Parent / parent and root / Root"
    assert (
        render_bulk_annotation(
            document, BulkAnnotationPreviewRequest(tier=2, asp_group="parent"), groups=groups
        ).rule_id
        == "gene_text"
    )
    assert (
        render_bulk_annotation(
            document, BulkAnnotationPreviewRequest(tier=2, asp_group="other"), groups=groups
        ).text
        is None
    )
    leaf = next(group for group in groups if group.group_id == "leaf")
    assert leaf.path_ids == ["leaf", "parent", "root"]


@pytest.mark.parametrize(
    "groups",
    [
        [{"group_id": "a", "parent_group_id": "missing"}],
        [{"group_id": "a", "parent_group_id": "b"}, {"group_id": "b", "parent_group_id": "a"}],
        [{"group_id": "a"}, {"group_id": "a"}],
        [{}],
    ],
)
def test_invalid_hierarchies_fail_before_rendering(groups):
    with pytest.raises(ValueError):
        bulk_annotation_group_options(groups)


def test_authoring_lists_parents_without_assays_and_preview_resolves_assay_group():
    from coyote3.application.reporting.clinical_rules.authoring import ClinicalRuleAuthoringService

    document = _document()
    document.bulk_annotation_rules = [
        _rule(
            condition={
                "type": "predicate",
                "fact": "asp.group_path_ids",
                "operator": "contains",
                "value": "root",
            },
            output=[{"type": "fact", "path": "asp.parent_group_name"}],
        )
    ]
    service = ClinicalRuleAuthoringService(
        SimpleNamespace(get=lambda _: document.model_dump(by_alias=True)),
        assay_group_repository=SimpleNamespace(list=_groups),
        assay_panel_repository=SimpleNamespace(
            get_all_asps=lambda **_: [
                {"asp_id": "assay_1", "asp_group": "leaf", "asp_category": "dna"}
            ]
        ),
        assay_diagnosis_repository=SimpleNamespace(list_for_assay=lambda *_args, **_kwargs: []),
    )
    options = service.authoring_options()
    assert set(options["condition_values"]["asp.group_path_ids"]) == {
        "root",
        "parent",
        "leaf",
        "other",
    }
    assert {group["group_id"] for group in options["bulk_annotation_groups"]} == {
        "root",
        "parent",
        "leaf",
        "other",
    }
    assert (
        service.preview_bulk_annotation("version", BulkAnnotationPreviewRequest(tier=2))["text"]
        == "Parent"
    )
    with pytest.raises(ValueError, match="not registered"):
        render_bulk_annotation(
            document,
            BulkAnnotationPreviewRequest(tier=2, asp_group="unknown"),
            groups=bulk_annotation_group_options(_groups()),
        )


def test_annotation_specific_facts_do_not_become_report_facts():
    document = _document()
    document.blocks[0].rules[0].output = [
        _rule(output=[{"type": "fact", "path": "annotation.oncokb_gene_url"}]).output[0]
    ]
    validation = validate_rule_set(document)
    assert not validation.valid
    assert any("unavailable" in error for error in validation.errors)


@pytest.mark.parametrize("present", [True, False, None])
def test_oncokb_presence_is_distinct_from_missing_context(present):
    document = _document()
    document.bulk_annotation_rules = [
        _rule(
            condition={
                "type": "predicate",
                "fact": "annotation.oncokb_gene_present",
                "operator": "eq",
                "value": True,
            },
            output=[
                {"type": "fact", "path": "annotation.consequence_text"},
                {"type": "text", "value": " / "},
                {"type": "fact", "path": "finding.transcript"},
                {"type": "text", "value": " / "},
                {"type": "fact", "path": "annotation.oncokb_gene_url"},
            ],
        ),
        _rule(
            rule_id="absent",
            order=20,
            condition={
                "type": "predicate",
                "fact": "annotation.oncokb_gene_present",
                "operator": "eq",
                "value": False,
            },
            output=[{"type": "text", "value": "Absent in local knowledgebase"}],
        ),
    ]
    result = render_bulk_annotation(
        document,
        BulkAnnotationPreviewRequest(
            tier=2,
            gene="GENE_A",
            transcript="NM_000001.1",
            consequence=["missense_variant"],
            oncokb_gene_present=present,
        ),
    )
    assert result.text == (
        "missense variant / NM_000001.1 / https://www.oncokb.org/gene/GENE_A"
        if present
        else "Absent in local knowledgebase"
        if present is False
        else None
    )


@pytest.mark.parametrize("tier", [1, 2, 3])
def test_bulk_templates_render_only_for_the_explicit_selected_tier(tier):
    """Text selection cannot assign or change a clinical tier."""
    document = _document()
    document.bulk_annotation_rules = [_rule(tier=tier)]
    assert validate_rule_set(document).valid
    result = render_bulk_annotation(
        document, BulkAnnotationPreviewRequest(tier=tier, gene="GENE_A")
    )
    assert result.rule_id == "gene_text"
    assert result.text == "**Reviewed** GENE_A"
    other = 2 if tier == 1 else 1
    assert (
        render_bulk_annotation(
            document, BulkAnnotationPreviewRequest(tier=other, gene="GENE_A")
        ).text
        is None
    )
    assert (
        render_bulk_annotation(
            document, BulkAnnotationPreviewRequest(tier=tier, gene="GENE_C")
        ).text
        is None
    )


def test_annotation_first_match_order_disabled_rules_and_explicit_fallback():
    document = _document()
    document.bulk_annotation_rules = [
        _rule(
            rule_id="fallback",
            order=100,
            condition=None,
            output=[{"type": "text", "value": "Fallback"}],
        ),
        _rule(rule_id="disabled", order=1, enabled=False),
        _rule(order=10),
    ]
    assert (
        render_bulk_annotation(
            document, BulkAnnotationPreviewRequest(tier=2, gene="GENE_A")
        ).rule_id
        == "gene_text"
    )
    assert (
        render_bulk_annotation(
            document, BulkAnnotationPreviewRequest(tier=2, gene="GENE_C")
        ).rule_id
        == "fallback"
    )


def test_annotation_templates_do_not_change_report_narrative():
    document = _document()
    evaluator = ClinicalRuleEvaluator()
    before = evaluator.evaluate(_context(), document, reporting_analyses={"SNV"})
    old_hash = content_hash(document)
    document.bulk_annotation_rules = [_rule()]
    after = evaluator.evaluate(_context(), document, reporting_analyses={"SNV"})
    assert before.sections == after.sections
    assert before.trace == after.trace
    assert old_hash != content_hash(document)


@pytest.mark.parametrize(
    "path", ["sample.name", "finding.case_vaf", "finding.cnv_copy_number", "aspc.environment"]
)
def test_reusable_annotations_reject_sample_specific_facts(path):
    document = _document()
    document.bulk_annotation_rules = [
        _rule(
            condition={
                "type": "not",
                "child": {"type": "predicate", "fact": path, "operator": "is_unknown"},
            },
            output=[{"type": "fact", "path": path}],
        )
    ]
    validation = validate_rule_set(document)
    assert not validation.valid
    assert any(f"Bulk annotations cannot use fact '{path}'" in error for error in validation.errors)


def test_annotations_reject_report_renderers_and_collection_conditions():
    document = _document()
    document.bulk_annotation_rules = [
        _rule(
            condition={
                "type": "collection_match",
                "collection": "findings",
                "quantifier": "any",
                "where": {
                    "type": "predicate",
                    "fact": "finding.gene",
                    "operator": "eq",
                    "value": "GENE_A",
                },
            },
            output=[{"type": "renderer", "name": "tier_summary"}],
        )
    ]
    validation = validate_rule_set(document)
    assert "Bulk annotations cannot use report collections" in validation.errors
    assert "Bulk annotations cannot use report sentence renderers" in validation.errors


def test_missing_required_output_fails_instead_of_writing_partial_text():
    document = _document()
    document.bulk_annotation_rules = [
        _rule(condition=None, output=[{"type": "fact", "path": "finding.hgvsp"}])
    ]
    with pytest.raises(ValueError, match="missing"):
        render_bulk_annotation(document, BulkAnnotationPreviewRequest(tier=2))


def test_any_condition_can_match_when_another_optional_fact_is_missing():
    """A matching gene alternative must not be discarded because HGVS is absent."""
    document = _document()
    document.bulk_annotation_rules = [
        _rule(
            condition={
                "type": "any",
                "children": [
                    {
                        "type": "predicate",
                        "fact": "finding.gene",
                        "operator": "eq",
                        "value": "GENE_A",
                    },
                    {
                        "type": "predicate",
                        "fact": "finding.hgvsp",
                        "operator": "eq",
                        "value": "p.Ala1Val",
                    },
                ],
            }
        )
    ]
    result = render_bulk_annotation(document, BulkAnnotationPreviewRequest(tier=2, gene="GENE_A"))
    assert result.rule_id == "gene_text"


def test_synthetic_preview_can_exercise_base_templates_for_a_named_diagnosis():
    document = _document()
    document.bulk_annotation_rules = [
        _rule(
            condition={
                "type": "predicate",
                "fact": "sample.diagnosis_id",
                "operator": "eq",
                "value": "scope_a",
            }
        )
    ]
    facts = BulkAnnotationPreviewRequest(tier=2, gene="GENE_A", diagnosis_id="scope_a")
    assert render_bulk_annotation(document, facts).rule_id == "gene_text"
    assert render_bulk_annotation(document, facts, diagnosis_id="scope_b").rule_id is None


def test_enabled_empty_annotation_text_cannot_enter_review():
    document = _document()
    document.bulk_annotation_rules = [_rule(output=[{"type": "text", "value": "  "}])]
    assert not validate_rule_set(document).valid
    document.bulk_annotation_rules[0].enabled = False
    assert validate_rule_set(document).valid


def test_additive_sections_are_valid_without_blanket_overlap_warnings():
    """Independent introduction and closing sentences intentionally use all matches."""
    document = _document()
    block = document.blocks[0]
    block.match_strategy = "all_matches"
    first = block.rules[0].model_copy(update={"condition": None})
    block.rules = [first, first.model_copy(update={"rule_id": "additional_sentence", "order": 100})]
    document.test_cases = []
    validation = validate_rule_set(document)
    assert validation.valid
    assert not any("overlapping conditions" in warning for warning in validation.warnings)


def test_first_match_warns_only_about_provably_unreachable_enabled_templates():
    document = _document()
    document.bulk_annotation_rules = [
        _rule(rule_id="fallback", order=1, condition=None),
        _rule(),
        _rule(rule_id="disabled", order=20, enabled=False),
    ]
    warnings = validate_rule_set(document).warnings
    assert any("'gene_text' is unreachable" in warning for warning in warnings)
    assert not any("'disabled' is unreachable" in warning for warning in warnings)
    document.bulk_annotation_rules[0].order = 100
    assert not any("unreachable" in warning for warning in validate_rule_set(document).warnings)


def test_base_templates_use_the_actual_diagnosis_scope():
    document = _document()
    document.bulk_annotation_rules = [
        _rule(
            condition={
                "type": "predicate",
                "fact": "sample.diagnosis_id",
                "operator": "eq",
                "value": "scope_a",
            }
        )
    ]
    facts = BulkAnnotationPreviewRequest(tier=2, gene="GENE_A")
    assert render_bulk_annotation(document, facts).text is None
    assert render_bulk_annotation(document, facts, diagnosis_id="scope_a").text


def test_duplicate_template_order_or_cross_destination_identity_is_rejected():
    document = _document().model_dump(by_alias=True)
    document["bulk_annotation_rules"] = [
        _rule().model_dump(),
        _rule(rule_id="duplicate_order").model_dump(),
    ]
    with pytest.raises(ValueError, match="orders must be unique"):
        ClinicalRuleSetDoc.model_validate(document)
    document["bulk_annotation_rules"] = [
        _rule(rule_id=document["blocks"][0]["rules"][0]["rule_id"]).model_dump()
    ]
    with pytest.raises(ValueError, match="rule IDs must be unique"):
        ClinicalRuleSetDoc.model_validate(document)


def test_generated_annotation_provenance_survives_the_storage_contract():
    """The real annotation builder and strict collection schema preserve template identity."""
    from coyote3.application.interpretation.report_summary import create_classified_variant_doc
    from coyote3.contracts.schemas.variant_annotations import AnnotationDoc

    document = create_classified_variant_doc(
        "p.Ala1Val",
        "p",
        2,
        {
            "asp_group": "synthetic",
            "asp_id": "assay_1",
            "diagnosis_id": "base",
            "namespace": "clinical",
            "gene": "GENE_A",
            "transcript": "NM_000001.1",
            "hgvsp": "p.Ala1Val",
            "hgvsc": "c.2C>T",
            "genomic": "1_2_C_T",
            "genomic_hash": "synthetic",
        },
        text="Reviewed annotation.",
    )
    document["rule_source"] = {
        "rule_set_id": "assay_1__base__sv",
        "content_version": 1,
        "revision": 2,
        "content_hash": "a" * 64,
        "rule_id": "gene_annotation",
        "tier": 2,
    }
    parsed = AnnotationDoc.model_validate(document)
    assert parsed.rule_source.rule_id == "gene_annotation"
    assert parsed.text == "Reviewed annotation."
    document.pop("text")
    document["class"] = 2
    with pytest.raises(ValueError, match="provenance requires text"):
        AnnotationDoc.model_validate(document)
