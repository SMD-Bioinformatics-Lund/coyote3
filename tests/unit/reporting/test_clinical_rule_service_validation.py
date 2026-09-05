"""Failure boundaries for rule resolution, validation, and fact preparation."""

from __future__ import annotations

from copy import deepcopy

import pytest

from api.application.reporting.clinical_rules.preparation import prepare_report_context
from api.application.reporting.clinical_rules.registry import (
    fact_catalog_payload,
    validate_fact_path,
)
from api.application.reporting.clinical_rules.service import ClinicalRuleService, rendered_summary
from api.application.reporting.clinical_rules.validation import (
    MAX_CONDITION_DEPTH,
    _validate_condition,
    content_hash,
    validate_rule_set,
)
from api.contracts.schemas.clinical_rules import (
    ClinicalMessageOutput,
    ClinicalRuleCollectionMatch,
    ClinicalRuleNot,
    ClinicalRulePredicate,
    ClinicalRuleTestCase,
)
from tests.unit.reporting.test_clinical_rules import _context, _document


def test_registry_accepts_known_facts_and_rejects_unknown_or_wrong_scope() -> None:
    assert validate_fact_path("sample.asp_id").kind == "string"
    assert fact_catalog_payload()[0]["path"] == "sample.asp_id"
    with pytest.raises(ValueError, match="Unsupported clinical rule fact"):
        validate_fact_path("sample.secret")
    with pytest.raises(ValueError, match="unavailable in once"):
        validate_fact_path("finding.gene", scope="once")


def test_service_from_store_and_resolution_failure_matrix() -> None:
    valid = _document(status="published", active=True)

    class Repository:
        def __init__(self, result):
            self.result = result

        def get_active(self, _rule_set_id):
            return deepcopy(self.result)

    assert isinstance(
        ClinicalRuleService.from_store(
            type("Store", (), {"clinical_rule_set_repository": Repository(valid.model_dump())})()
        ),
        ClinicalRuleService,
    )

    missing_binding = _context()
    missing_binding.aspc.reporting.clinical_rule_set_id = ""
    with pytest.raises(ValueError, match="does not define"):
        ClinicalRuleService(Repository(None)).resolve(context=missing_binding)

    with pytest.raises(ValueError, match="No active published"):
        ClinicalRuleService(Repository(None)).resolve(context=_context())

    too_new = valid.model_copy(update={"minimum_engine_version": 2})
    with pytest.raises(ValueError, match="requires engine version"):
        ClinicalRuleService(Repository(too_new.model_dump(mode="python", by_alias=True))).resolve(
            context=_context()
        )

    wrong_analyte = valid.model_copy(deep=True)
    wrong_analyte.scope.analyte = "rna"
    wrong_analyte.content_hash = content_hash(wrong_analyte)
    with pytest.raises(ValueError, match="analyte does not match"):
        ClinicalRuleService(
            Repository(wrong_analyte.model_dump(mode="python", by_alias=True))
        ).resolve(context=_context())

    corrupt = valid.model_copy(update={"name": "Changed after publication"})
    with pytest.raises(ValueError, match="integrity validation"):
        ClinicalRuleService(Repository(corrupt.model_dump(mode="python", by_alias=True))).resolve(
            context=_context()
        )


def test_service_rejects_undeclared_sections_and_delegates_valid_evaluation() -> None:
    document = _document(status="published", active=True)
    repository = type(
        "Repository",
        (),
        {
            "get_active": lambda self, _rule_set_id: document.model_dump(
                mode="python", by_alias=True
            )
        },
    )()
    context = _context()
    context.aspc.reporting.report_sections = ["SNV", "  ", "TMB"]
    with pytest.raises(ValueError, match="TMB"):
        ClinicalRuleService(repository).evaluate(aspc={}, context=context)

    context.aspc.reporting.report_sections = ["snv"]
    assert ClinicalRuleService(repository).evaluate(aspc={}, context=context).sections


def test_rendered_summary_handles_none_empty_heading_and_unheaded_sections() -> None:
    assert rendered_summary(None) == ""
    evaluation = ClinicalRuleService(
        type(
            "Repository",
            (),
            {
                "get_active": lambda self, _id: _document(
                    status="published", active=True
                ).model_dump(mode="python", by_alias=True)
            },
        )()
    ).evaluate(aspc={}, context=_context())
    evaluation.sections["Empty"] = []
    evaluation.sections["Plain"] = ["No heading"]
    evaluation.section_headings["Plain"] = False
    text = rendered_summary(evaluation)
    assert "## Findings" in text
    assert "No heading" in text
    assert "## Plain" not in text


def test_validation_reports_structural_condition_and_embedded_case_failures(monkeypatch) -> None:
    document = _document()
    document.minimum_engine_version = 2
    document.analysis_declarations["CNV"].narrative = "enabled"
    document.blocks[1].section = document.blocks[0].section
    document.blocks[0].rules[0].output[1].path = "sample.secret"
    document.blocks[0].rules[0].condition = ClinicalRuleNot(
        child=ClinicalRuleCollectionMatch(
            collection="findings",
            quantifier="any",
            where=ClinicalRulePredicate(fact="item.gene", operator="eq", value="TP53"),
        )
    )
    errors: list[str] = []
    deeply_nested = ClinicalRulePredicate(fact="sample.asp_id", operator="eq", value="assay_1")
    _validate_condition(deeply_nested, scope="once", depth=MAX_CONDITION_DEPTH + 1, errors=errors)
    assert "nesting exceeds" in errors[0]
    unsupported_errors: list[str] = []
    _validate_condition(object(), scope="once", depth=1, errors=unsupported_errors)  # type: ignore[arg-type]
    assert "Unsupported clinical condition" in unsupported_errors[0]
    result = validate_rule_set(document)
    assert result.valid is False
    assert any("engine version" in error for error in result.errors)
    assert any("enabled but has no enabled" in warning for warning in result.warnings)
    assert any("mixes heading visibility" in error for error in result.errors)
    assert any("sample.secret" in error for error in result.errors)

    no_blocks = document.model_copy(deep=True)
    no_blocks.blocks = []
    assert any("At least one rule block" in error for error in validate_rule_set(no_blocks).errors)

    undeclared = _document()
    undeclared.analysis_declarations.pop("SNV")
    undeclared.blocks[0].rules[0].condition = ClinicalRulePredicate(
        fact="unsupported.fact", operator="eq", value="x"
    )
    undeclared.blocks[0].rules[0].output.append(
        ClinicalMessageOutput(count_path="aggregates.finding_count", one="one", other="many")
    )
    undeclared.blocks[1].rules = []
    undeclared.test_cases = [
        ClinicalRuleTestCase.model_validate(
            {
                "test_id": "not-run",
                "name": "Not run after structural errors",
                "facts": {},
            }
        )
    ]
    result = validate_rule_set(undeclared)
    assert any("not declared as enabled" in error for error in result.errors)
    assert any("unsupported.fact" in error for error in result.errors)
    assert any("must contain at least one rule" in error for error in result.errors)


def test_validation_embedded_case_handles_invalid_facts_and_rule_mismatch() -> None:
    document = _document()
    valid_facts = _context().model_dump(mode="python")
    document.test_cases = [
        ClinicalRuleTestCase.model_validate(
            {
                "test_id": "invalid",
                "name": "Invalid facts",
                "facts": {},
                "expected_rule_ids": [],
                "expected_sections": {},
            }
        )
    ]
    parsed = type(document).model_validate(document.model_dump(mode="python", by_alias=True))
    result = validate_rule_set(parsed)
    assert any("could not be evaluated" in error for error in result.errors)

    document.test_cases = [
        ClinicalRuleTestCase.model_validate(
            {
                "test_id": "mismatch",
                "name": "Mismatch",
                "facts": valid_facts,
                "expected_rule_ids": [],
                "expected_sections": {"wrong": []},
            }
        )
    ]
    parsed = type(document).model_validate(document.model_dump(mode="python", by_alias=True))
    result = validate_rule_set(parsed)
    assert any("matched" in error for error in result.errors)
    assert any("unexpected report text" in error for error in result.errors)


def test_preparation_handles_invalid_fallback_values_and_structural_edge_shapes() -> None:
    context = prepare_report_context(
        sample={
            "name": "SYNTHETIC",
            "asp_id": "assay_1",
            "subpanel_id": "base",
            "environment": "testing",
        },
        asp={"asp_id": "assay_1"},
        aspc={
            "aspc_id": "config",
            "asp_id": "assay_1",
            "subpanel_id": "base",
            "environment": "testing",
            "reporting": {"clinical_rule_set_id": "assay_1__base__sv"},
        },
        analyte="dna",
        applied_gene_lists=[{"isgl_id": "list", "list_type": "snv"}],
        report_sections_data={
            "snvs": [
                {
                    "symbol": "TP53",
                    "af": "invalid",
                    "GT": [{"type": "control", "AF": "invalid"}],
                    "consequence": "missense_variant&splice_region_variant",
                    "exon": "7/11",
                    "intron": "6/10",
                    "class": 2,
                }
            ],
            "cnvs": [
                {"genes": ["bad", {"gene": "TP53"}], "ratio": -0.5},
                {"genes": [{"gene": "A"}, {"gene": "B"}], "effect": "gain"},
            ],
            "fusions": [
                {
                    "INFO": {"ANN": [], "MANE_ANN": {}},
                    "calls": "wrong",
                    "global_annotations": [{"text": "", "hidden": False}, "bad"],
                }
            ],
        },
    )
    assert context.findings[0].case_vaf is None
    assert context.findings[0].control_vaf is None
    assert context.findings[1].cnv_effect == "loss"
    assert context.findings[2].gene is None
    assert context.findings[3].genes == []
    assert context.applied_gene_lists[0].list_type == ["snv"]

    mane_context = prepare_report_context(
        sample={"name": "S", "asp_id": "assay_1", "environment": "testing"},
        asp={"asp_id": "assay_1"},
        aspc={
            "aspc_id": "c",
            "asp_id": "assay_1",
            "environment": "testing",
            "reporting": {"clinical_rule_set_id": "assay_1__base__sv"},
        },
        analyte="dna",
        applied_gene_lists=[{"isgl_id": "list", "list_type": ["snv"]}],
        report_sections_data={"fusions": [{"INFO": {"MANE_ANN": {"Gene_Name": "A&B"}}}]},
    )
    assert mane_context.findings[0].genes == ["A", "B"]
