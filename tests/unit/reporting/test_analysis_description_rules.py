"""Analysis descriptions use governed rules independently of report summaries."""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from coyote3.application.reporting.clinical_rules.resolution import capture_clinical_rules
from coyote3.application.reporting.clinical_rules.service import (
    ClinicalRuleService,
    rendered_summary,
)
from coyote3.application.reporting.clinical_rules.validation import content_hash, validate_rule_set
from coyote3.application.reporting.report_context import prepare_render_context
from coyote3.contracts.schemas.assay import AspcReportingDoc
from coyote3.contracts.schemas.clinical_rules import ClinicalRuleBlock
from tests.unit.reporting.test_clinical_rules import _configuration, _context, _document


def _description_block(*, enabled=True, condition=None):
    """Build two method paragraphs using a dynamic assay identifier and a condition."""
    return ClinicalRuleBlock.model_validate(
        {
            "block_id": "method",
            "name": "Analysis description",
            "section": "analysis_description",
            "section_order": 300,
            "block_order": 1,
            "show_heading": False,
            "match_strategy": "all_matches",
            "rules": [
                {
                    "rule_id": "method_scope",
                    "name": "Assay scope",
                    "order": 1,
                    "enabled": enabled,
                    "condition": condition,
                    "output": [
                        {"type": "text", "value": "Method for "},
                        {"type": "fact", "path": "sample.asp_id"},
                        {"type": "text", "value": "."},
                    ],
                },
                {
                    "rule_id": "method_limits",
                    "name": "Method limitations",
                    "order": 2,
                    "enabled": enabled,
                    "condition": condition,
                    "output": [{"type": "text", "value": "Reviewed limitations."}],
                },
            ],
        }
    )


def _service(*documents):
    """Resolve supplied publications using the production assay/scope filtering."""
    return ClinicalRuleService(
        SimpleNamespace(
            list_active_for_assay=lambda *args, **kwargs: [
                document.model_dump(mode="python", by_alias=True) for document in documents
            ]
        )
    )


def test_description_is_dynamic_and_separate_from_summary():
    document = _document(status="published", active=True)
    document.blocks.append(_description_block())
    document.content_hash = content_hash(document)
    evaluation = _service(document).evaluate(aspc=_configuration(document), context=_context())
    assert evaluation.sections["analysis_description"] == [
        "Method for assay_1.",
        "Reviewed limitations.",
    ]
    assert "Method for" not in rendered_summary(evaluation)
    assert "Finding in TP53" in rendered_summary(evaluation)
    context = prepare_render_context(
        {"clinical_rule_evaluation": evaluation.model_dump(mode="json")},
        analyte="dna",
        preview=True,
    )
    assert context["analysis_description"] == "Method for assay_1.\n\nReviewed limitations."


@pytest.mark.parametrize("override", ["absent", "enabled", "disabled", "unmatched"])
def test_diagnosis_description_inheritance_and_explicit_override(override):
    base = _document(status="published", active=True)
    base.blocks.append(_description_block())
    base.content_hash = content_hash(base)
    exact = _document(status="published", active=True)
    exact.scope.diagnosis_id = "myeloid"
    exact.rule_set_id = "assay_1__myeloid__sv"
    if override != "absent":
        condition = (
            {"type": "predicate", "fact": "sample.paired", "operator": "eq", "value": True}
            if override == "unmatched"
            else None
        )
        block = _description_block(enabled=override != "disabled", condition=condition)
        block.rules[0].output[0].value = "Diagnosis method for "
        exact.blocks.append(block)
    exact.content_hash = content_hash(exact)
    context = _context()
    context.sample.diagnosis_id = "myeloid"
    with capture_clinical_rules() as sources:
        evaluation = _service(exact, base).evaluate(
            aspc=_configuration(exact, context),
            context=context,
        )
    assert evaluation.source.rule_set_oid == str(exact.id_)
    if override == "absent":
        assert evaluation.sections["analysis_description"][0] == "Method for assay_1."
        assert evaluation.analysis_description_source.rule_set_oid == str(base.id_)
        assert set(sources) == {exact.rule_set_id, base.rule_set_id}
        assert sum(entry.rule_id == "positive" for entry in evaluation.trace) == 1
    elif override == "enabled":
        assert evaluation.sections["analysis_description"][0] == "Diagnosis method for assay_1."
        assert evaluation.analysis_description_source is None
    else:
        assert "analysis_description" not in evaluation.sections
        assert evaluation.analysis_description_source is None


def test_missing_description_renders_no_method_text():
    context = prepare_render_context(
        {},
        analyte="dna",
        preview=True,
    )
    assert context["analysis_description"] == ""


def test_description_cannot_override_the_report_section_heading():
    document = _document()
    block = _description_block()
    block.show_heading = True
    document.blocks.append(block)
    assert any("fixed section heading" in error for error in validate_rule_set(document).errors)


def test_aspc_description_is_removed_from_the_strict_contract():
    reporting = dict(
        report_header="Synthetic report",
        report_method="Synthetic method",
        plots_path="plots",
        report_folder="reports",
    )
    assert "report_description" not in AspcReportingDoc.model_validate(reporting).model_dump()
    with pytest.raises(ValidationError, match="Extra inputs"):
        AspcReportingDoc.model_validate({**reporting, "report_description": "Obsolete"})
