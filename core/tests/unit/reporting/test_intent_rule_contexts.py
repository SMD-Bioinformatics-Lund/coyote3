"""Profile-targeted report rules consume isolated facts without inventing clinical text."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from core_test_support.clinical_rules import _context, _document
from coyote.application.common.release_resources import capture_gene_lists
from coyote.application.reporting.clinical_rules.evaluator import ClinicalRuleEvaluator
from coyote.application.reporting.clinical_rules.preparation import prepare_snv_profile_context
from coyote.application.reporting.clinical_rules.service import ClinicalRuleService
from coyote.application.reporting.clinical_rules.validation import content_hash, validate_rule_set
from coyote.contracts.schemas.clinical_rules import ClinicalRuleBlock


def profile_contexts():
    """Use distinct SNVs and a pinned germline list for one synthetic sample."""
    primary = _context()
    primary.aspc.snv_filter_mode = "independent"
    primary.asp.germline_genes = ["BRCA1", "BRCA2"]
    configuration = primary.aspc.model_dump()
    configuration["gene_list_release"] = capture_gene_lists(
        [{"isgl_id": "synthetic-germline", "genes": ["BRCA1", "BRCA2"], "list_type": ["snv"]}]
    )
    germline = prepare_snv_profile_context(
        sample=primary.sample.model_dump(),
        asp=primary.asp.model_dump(),
        aspc=configuration,
        sample_filters={"germline": {"snv": {"snvlists": ["synthetic-germline"]}}},
        findings=[
            {"INFO": {"selected_CSQ": {"SYMBOL": gene}}, "classification": {"class": 2}}
            for gene in ("BRCA1", "BRCA2")
        ],
        intent="germline",
    )
    return primary, germline


def narrative_block(identifier, intent=None, *, section=None, order=1):
    """Provide synthetic output only; no production clinical wording is seeded."""
    return ClinicalRuleBlock.model_validate(
        {
            "block_id": identifier,
            "name": identifier,
            "analysis": "SNV",
            "analysis_intent": intent,
            "section": section or identifier,
            "section_order": order,
            "block_order": order,
            "show_heading": False,
            "match_strategy": "all_matches",
            "rules": [
                {
                    "rule_id": identifier,
                    "name": identifier,
                    "order": 1,
                    "output": [{"type": "text", "value": f"synthetic-{identifier}"}],
                }
            ],
        }
    )


def test_missing_germline_rules_do_not_copy_primary_narrative():
    primary, germline = profile_contexts()
    document = _document()
    document.blocks = [narrative_block("primary")]
    engine = ClinicalRuleEvaluator()
    result = engine.evaluate(
        primary, document, reporting_analyses={"SNV"}, intent_contexts={"germline": germline}
    )
    assert result.sections == {"primary": ["synthetic-primary"]}
    assert len(result.trace) == 1
    assert engine.evaluate(germline, document, reporting_analyses={"SNV"}).sections == {}


@pytest.mark.parametrize("intent", ["somatic", "germline"])
def test_each_profile_can_supply_a_standalone_independent_narrative(intent):
    primary, germline = profile_contexts()
    context = primary if intent == "somatic" else germline
    document = _document()
    document.blocks = [narrative_block("standalone", intent)]
    result = ClinicalRuleEvaluator().evaluate(context, document, reporting_analyses={"SNV"})
    assert result.sections == {"standalone": ["synthetic-standalone"]}


def test_shared_flow_retains_untargeted_rules_and_existing_content_hash():
    primary, _ = profile_contexts()
    primary.aspc.snv_filter_mode = "shared"
    document = _document()
    block = narrative_block("shared")
    document.blocks = [block]
    original_hash = content_hash(document)
    serialized = document.model_dump()
    assert "analysis_intent" not in serialized["blocks"][0]
    assert content_hash(type(document).model_validate(serialized)) == original_hash
    result = ClinicalRuleEvaluator().evaluate(primary, document, reporting_analyses={"SNV"})
    assert result.sections == {"shared": ["synthetic-shared"]}


def test_future_germline_rules_use_their_own_findings_counts_and_lists():
    primary, germline = profile_contexts()
    document = _document()
    block = narrative_block("future-germline", "germline")
    authored = block.model_dump()
    authored["rules"][0]["output"] = [
        {"type": "number", "path": "aggregates.snv_count", "precision": 0, "unit": ""},
        {"type": "text", "value": " "},
        {
            "type": "list",
            "path": "gene_lists.snv.genes",
            "conjunction": "and",
            "formatter": "gene_symbol",
        },
    ]
    # Validate authored output through the same contract used by rule editing.
    document.blocks = [
        narrative_block("primary"),
        ClinicalRuleBlock.model_validate(authored),
    ]
    document.content_hash = content_hash(document)
    assert validate_rule_set(document).valid
    result = ClinicalRuleService(SimpleNamespace()).evaluate_document(
        rule_set=document, context=primary, intent_contexts={"germline": germline}
    )
    text = " ".join(result.sections["future-germline"])
    assert text.startswith("2") and "BRCA1" in text and "BRCA2" in text
    assert "TP53" not in text
    assert primary.aggregates.snv_count == 1
    assert germline.aggregates.snv_count == 2
    assert germline.aspc.snv_filter_mode == "independent"


def test_germline_sections_are_inactive_without_their_profile_or_snv_reporting():
    primary, germline = profile_contexts()
    document = _document()
    document.blocks = [narrative_block("germline", "germline")]
    engine = ClinicalRuleEvaluator()
    assert engine.evaluate(primary, document, reporting_analyses={"SNV"}).sections == {}
    assert (
        engine.evaluate(
            primary, document, reporting_analyses={"CNV"}, intent_contexts={"germline": germline}
        ).sections
        == {}
    )


@pytest.mark.parametrize("change", ["sample", "configuration", "mode", "key"])
def test_profile_contexts_cannot_cross_sample_or_configuration_boundaries(change):
    primary, germline = profile_contexts()
    key = "germline"
    if change == "sample":
        germline.sample.name = "ANOTHER_SYNTHETIC_SAMPLE"
    elif change == "configuration":
        germline.aspc.aspc_id = "another-configuration"
    elif change == "mode":
        primary.aspc.snv_filter_mode = germline.aspc.snv_filter_mode = "shared"
    else:
        key = "somatic"
    with pytest.raises(ValueError):
        ClinicalRuleEvaluator().evaluate(
            primary, _document(), reporting_analyses={"SNV"}, intent_contexts={key: germline}
        )


def test_additional_profile_cannot_replace_primary_findings():
    """Reject replacement facts even when sample and configuration identities agree."""
    primary, _ = profile_contexts()
    replacement = primary.model_copy(deep=True)
    replacement.aggregates.snv_count += 1
    with pytest.raises(ValueError, match="cannot replace primary facts"):
        ClinicalRuleEvaluator().evaluate(
            primary,
            _document(),
            reporting_analyses={"SNV"},
            intent_contexts={"somatic": replacement},
        )


def test_strict_conflicts_are_checked_within_each_profile():
    primary, germline = profile_contexts()
    document = _document()
    document.blocks = [
        narrative_block("somatic", "somatic"),
        narrative_block("germline", "germline", order=2),
    ]
    for block in document.blocks:
        block.match_strategy, block.conflict_group = "exactly_one", "summary"
    assert validate_rule_set(document).valid
    result = ClinicalRuleEvaluator().evaluate(
        primary, document, reporting_analyses={"SNV"}, intent_contexts={"germline": germline}
    )
    assert set(result.sections) == {"somatic", "germline"}
    duplicate = narrative_block("conflicting-germline", "germline", order=3)
    duplicate.match_strategy, duplicate.conflict_group = "exactly_one", "summary"
    document.blocks.append(duplicate)
    with pytest.raises(ValueError, match="Conflict group"):
        ClinicalRuleEvaluator().evaluate(
            primary, document, reporting_analyses={"SNV"}, intent_contexts={"germline": germline}
        )


def test_base_method_wording_inherits_independently_for_each_profile():
    primary, germline = profile_contexts()
    for context in (primary, germline):
        context.sample.diagnosis_id = context.aspc.diagnosis_id = "synthetic-diagnosis"
    base = _document(status="published", active=True)
    base.blocks = [
        narrative_block("base-primary", section="analysis_description"),
        narrative_block("base-germline", "germline", section="analysis_description", order=2),
    ]
    base.content_hash = content_hash(base)
    selected = _document(status="published", active=True)
    selected.scope.diagnosis_id = "synthetic-diagnosis"
    selected.rule_set_id = "assay_1__synthetic-diagnosis__sv"
    selected.blocks = [narrative_block("selected-primary", section="analysis_description")]
    selected.content_hash = content_hash(selected)
    repository = SimpleNamespace(
        list_active_for_assay=lambda *args, **kwargs: [
            deepcopy(document.model_dump(mode="python", by_alias=True))
            for document in (base, selected)
        ]
    )
    result = ClinicalRuleService(repository).evaluate_document(
        rule_set=selected, context=primary, intent_contexts={"germline": germline}
    )
    assert result.sections["analysis_description"] == [
        "synthetic-selected-primary",
        "synthetic-base-germline",
    ]
    assert result.analysis_description_source.rule_set_id == base.rule_set_id


def test_inherited_method_wording_cannot_mix_heading_modes():
    """Prevent Base wording from changing a diagnosis section's heading presentation."""
    primary, germline = profile_contexts()
    for context in (primary, germline):
        context.sample.diagnosis_id = context.aspc.diagnosis_id = "synthetic-diagnosis"
    base = _document(status="published", active=True)
    base.blocks = [narrative_block("base-germline", "germline", section="analysis_description")]
    base.content_hash = content_hash(base)
    selected = _document(status="published", active=True)
    selected.scope.diagnosis_id = "synthetic-diagnosis"
    selected.rule_set_id = "assay_1__synthetic-diagnosis__sv"
    selected.blocks = [narrative_block("selected-primary", section="analysis_description")]
    selected.blocks[0].show_heading = True
    selected.content_hash = content_hash(selected)
    repository = SimpleNamespace(
        list_active_for_assay=lambda *args, **kwargs: [
            deepcopy(document.model_dump(mode="python", by_alias=True))
            for document in (base, selected)
        ]
    )
    with pytest.raises(ValueError, match="analysis_description.*mixes heading modes"):
        ClinicalRuleService(repository).evaluate_document(
            rule_set=selected, context=primary, intent_contexts={"germline": germline}
        )


@pytest.mark.parametrize(
    "section,analysis,analyte",
    [
        ("clinical_question", "SNV", "dna"),
        ("Summary", "CNV", "dna"),
        ("Summary", None, "rna"),
    ],
)
def test_profile_targets_cannot_relabel_metadata_or_unsupported_analyses(
    section, analysis, analyte
):
    document = _document()
    document.scope.analyte = analyte
    block = narrative_block("invalid", "germline", section=section)
    block.analysis = analysis
    document.blocks = [block]
    assert not validate_rule_set(document).valid
    primary, _ = profile_contexts()
    primary.sample.asp_category = analyte
    with pytest.raises(ValueError, match="metadata|DNA SNVs"):
        ClinicalRuleEvaluator().evaluate(primary, document, reporting_analyses={"SNV", "CNV"})
