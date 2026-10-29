"""CNV evidence calculations and governed report-summary regressions."""

from copy import deepcopy

import pytest

from coyote3.application.reporting.clinical_rules.evaluator import ClinicalRuleEvaluator
from coyote3.application.reporting.clinical_rules.preparation import prepare_report_context
from coyote3.application.reporting.clinical_rules.registry import fact_catalog_payload
from coyote3.application.reporting.clinical_rules.renderers import render_cnv_summary
from coyote3.application.reporting.clinical_rules.service import rendered_summary
from coyote3.application.reporting.clinical_rules.validation import validate_rule_set
from coyote3.contracts.schemas.clinical_rules import (
    ClinicalAnalysisDeclaration,
    ClinicalRule,
    ClinicalRuleBlock,
    ClinicalRuleTestCase,
)
from coyote3.domain.common.reporting import STANDARD_CNV_SUMMARY_PHRASES
from coyote3.domain.dna.cnv_metrics import supporting_read_percent
from tests.unit.reporting.test_clinical_rules import _document


def _context(cnvs):
    """Prepare synthetic CNVs through the production report fact boundary."""
    return prepare_report_context(
        sample={"name": "SYNTHETIC_CNV", "asp_id": "assay_1"},
        asp={},
        aspc={"reporting": {"report_sections": ["CNV"]}},
        analyte="dna",
        applied_gene_lists=[],
        report_sections_data={"cnvs": cnvs},
    )


def _cnv(*, gene="TP53", ratio=1.0, callers=("gatk",), **extra):
    """Build one reviewed copy-number call with a classified gene."""
    return {
        "interesting": True,
        "genes": [{"gene": gene, "class": 1}],
        "ratio": ratio,
        "callers": list(callers),
        **extra,
    }


def _rules():
    """Configure the named CNV renderer as an explicitly governed output."""
    document = _document()
    document.analysis_declarations = {"CNV": ClinicalAnalysisDeclaration(narrative="enabled")}
    document.terminology = {"cnv_summary": deepcopy(STANDARD_CNV_SUMMARY_PHRASES)}
    document.blocks = [
        ClinicalRuleBlock.model_validate(
            {
                "block_id": "cnv",
                "name": "CNV summary",
                "analysis": "CNV",
                "section": "CNV",
                "section_order": 1,
                "block_order": 1,
                "match_strategy": "at_most_one",
                "rules": [
                    {
                        "rule_id": "cnv_present",
                        "name": "Reviewed CNV groups",
                        "order": 1,
                        "condition": {
                            "type": "predicate",
                            "fact": "aggregates.cnv_summary_count",
                            "operator": "gt",
                            "value": 0,
                        },
                        "output": [{"type": "renderer", "name": "cnv_summary"}],
                    }
                ],
            }
        )
    ]
    return document


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("90,10", 10.0),
        ("90/10", 10.0),
        ([2, 1], 33.3),
        ((0, 5), 100.0),
        ("5,0", 0.0),
        ("0,0", None),
        (None, None),
        (0, None),
        ("invalid", None),
        ("1,2,3", None),
        ("-1,2", None),
        ("nan,2", None),
        ("inf,1", None),
        ("0.5,2", None),
        ([True, 1], None),
        ([None, 1], None),
    ],
)
def test_read_percent_distinguishes_observed_zero_from_missing_evidence(value, expected):
    assert supporting_read_percent(value) == expected


@pytest.mark.parametrize(
    ("ratio", "expected"),
    [
        (1.0, 4.0),
        (-1.0, 1.0),
        (0, 2.0),
        (0.5, 2.83),
        (None, None),
        (float("nan"), None),
        (float("inf"), None),
        (2000, None),
        (True, None),
    ],
)
def test_prepared_copy_number_uses_diploid_baseline_without_purity_adjustment(ratio, expected):
    context = _context([_cnv(ratio=ratio, PR="90,10", SR="2/1")])
    finding = context.findings[0]
    assert finding.cnv_copy_number == expected
    assert finding.cnv_paired_read_percent == 10.0
    assert finding.cnv_split_read_percent == 33.3


def test_grouped_summary_matches_master_caller_selection_and_gene_grouping():
    cnvs = [
        _cnv(ratio=1.0, genes=[{"gene": "TP53", "class": 1}, {"gene": "OTHER"}]),
        _cnv(
            ratio=2.0,
            callers=("cnvkit",),
            genes=[{"gene": "TP53", "class": 1}, {"gene": "OTHER"}, {"gene": "OTHER2"}],
        ),
        _cnv(ratio=0.5, callers=("manta",), PR="90,10", SR="80,20"),
        _cnv(gene="CDKN2A", ratio=-1.0),
        _cnv(gene="CDKN2A", ratio=-2.0),
        _cnv(gene="MYC", ratio=1.0),
    ]
    before = deepcopy(cnvs)
    context = _context(cnvs)
    assert cnvs == before
    groups = context.aggregates.cnv_summaries
    assert context.aggregates.cnv_summary_count == 3
    assert groups[0].copy_number == 8.0
    assert groups[0].other_gene_count == 2
    assert groups[0].paired_read_percent == 10.0
    assert groups[0].split_read_percent == 20.0
    assert groups[1].copy_number == 1.0
    assert context.findings[0].genes == ["TP53", "OTHER"]
    assert context.findings[0].cnv_report_genes == ["TP53"]
    expected = (
        "Vid analysen finner man en amplifiering av genen TP53 (cn=8.0 i 10.0% av "
        "överspännande läsningar och 20.0% av splittade läsningar). "
        "Vidare finner man en förlust av genen CDKN2A (cn=1.0). "
        "Slutligen finner man en amplifiering av genen MYC (cn=4.0). "
    )
    rules = _rules()
    evaluation = ClinicalRuleEvaluator().evaluate(context, rules, reporting_analyses={"CNV"})
    assert evaluation.sections == {"CNV": [expected]}
    assert expected in rendered_summary(evaluation)
    rules.test_cases = [
        ClinicalRuleTestCase(
            test_id="reviewed_cnv",
            name="Reviewed CNVs",
            facts=context.model_dump(mode="json"),
            expected_rule_ids=["cnv_present"],
            expected_sections={"CNV": [expected]},
        )
    ]
    result = validate_rule_set(rules, require_tests=True)
    assert result.valid, result.errors
    excluded = ClinicalRuleEvaluator().evaluate(context, rules, reporting_analyses={"SNV"})
    assert excluded.sections == {}


def test_unreviewed_unclassified_and_unknown_effect_calls_do_not_create_summary_groups():
    context = _context(
        [
            _cnv(interesting=False),
            _cnv(interesting=None),
            _cnv(genes=[{"gene": "UNCLASSIFIED"}]),
            _cnv(ratio=None),
            _cnv(ratio=None, type="DEL", callers=("manta",), SR="0,0"),
        ]
    )
    assert len(context.findings) == 5
    assert context.aggregates.cnv_summary_count == 1
    evaluation = ClinicalRuleEvaluator().evaluate(context, _rules(), reporting_analyses={"CNV"})
    assert evaluation.sections == {"CNV": ["Vid analysen finner man en förlust av genen TP53. "]}


def test_manta_last_valid_support_wins_and_missing_support_does_not_erase_evidence():
    context = _context(
        [
            _cnv(callers=("manta",), PR="90,10", SR="80,20"),
            _cnv(callers=("manta",), PR="100,0", SR="0,0"),
            _cnv(callers=("manta",), PR="invalid", SR=None),
        ]
    )
    group = context.aggregates.cnv_summaries[0]
    assert group.copy_number is None
    assert group.paired_read_percent == 0.0
    assert group.split_read_percent == 20.0


@pytest.mark.parametrize(
    ("support", "expected"),
    [
        ({"PR": "90,10"}, " ( i 10.0% av överspännande läsningar)"),
        ({"SR": "80,20"}, " ( i 20.0% av splittade läsningar)"),
        ({"PR": "0,0", "SR": "invalid"}, ""),
    ],
)
def test_structural_evidence_and_plural_genes_use_rule_owned_wording(support, expected):
    context = _context(
        [
            _cnv(
                callers=("manta",),
                genes=[{"gene": "TP53", "class": 1}, {"gene": "MYC", "class": 2}],
                **support,
            )
        ]
    )
    rules = _rules()
    rules.terminology["cnv_summary"]["first_prefix"] = "Reviewed: "
    evaluation = ClinicalRuleEvaluator().evaluate(context, rules, reporting_analyses={"CNV"})
    assert evaluation.sections["CNV"] == [
        "Reviewed: amplifiering av generna TP53 samt MYC" + expected + ". "
    ]


def test_calculated_values_are_available_as_typed_inline_output():
    context = _context([_cnv(PR="90,10")])
    rules = _rules()
    rules.blocks[0].evaluation.mode = "each_finding"
    output = [
        {"type": "text", "value": "Copy number: "},
        {"type": "number", "path": "finding.cnv_copy_number", "precision": 1},
        {"type": "text", "value": "; support: "},
        {"type": "number", "path": "finding.cnv_paired_read_percent", "precision": 1, "unit": "%"},
    ]
    rules.blocks[0].rules[0] = ClinicalRule.model_validate(
        {
            **rules.blocks[0].rules[0].model_dump(),
            "output": output,
        }
    )
    evaluation = ClinicalRuleEvaluator().evaluate(context, rules, reporting_analyses={"CNV"})
    assert evaluation.sections["CNV"] == ["Copy number: 4.0; support: 10.0%"]
    paths = {fact["path"] for fact in fact_catalog_payload()}
    assert {
        "finding.cnv_copy_number",
        "finding.cnv_paired_read_percent",
        "finding.cnv_split_read_percent",
        "aggregates.cnv_summaries",
    } <= paths


def test_missing_cnv_terminology_is_an_explicit_error():
    with pytest.raises(ValueError, match="cnv_summary"):
        render_cnv_summary([], {})
