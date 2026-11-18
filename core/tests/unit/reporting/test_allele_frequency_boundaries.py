# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Invalid allele measurements must not become clinical evidence or report percentages."""

import pytest
from core_test_support.report_presentation import structural_context
from core_test_support.smd_input import document, sections
from coyote.application.reporting.clinical_rules.preparation import prepare_report_context
from coyote.contracts.schemas.dna import VariantGtDoc
from pydantic import ValidationError


@pytest.mark.parametrize("frequency", [True, False, float("nan"), float("inf"), -0.1, 1.1])
def test_genotype_contract_rejects_unusable_allele_fractions(frequency):
    with pytest.raises(ValidationError):
        VariantGtDoc(AF=frequency, DP=20, VD=10, GT="0/1", sample="SYNTHETIC", type="case")


@pytest.mark.parametrize("frequency", [True, float("nan"), float("inf"), -0.1, 1.1])
def test_invalid_stored_fractions_are_unavailable_to_report_rules(frequency):
    context = prepare_report_context(
        sample={"name": "SYNTHETIC", "asp_id": "panel"},
        asp={},
        aspc={},
        analyte="dna",
        applied_gene_lists=[],
        report_sections_data={
            "snvs": [
                {
                    "symbol": "TP53",
                    "af": 0.5,
                    "GT": [{"type": "case", "AF": frequency}, {"type": "control", "AF": frequency}],
                }
            ]
        },
    )
    finding = context.findings[0]
    assert finding.case_vaf is None and finding.case_vaf_percent is None
    assert finding.control_vaf is None and finding.control_vaf_percent is None


@pytest.mark.parametrize(
    "frequency,expected",
    [
        (True, "-"),
        ("NaN", "-"),
        ("Infinity", "-"),
        (-0.1, "-"),
        (1.1, "-"),
        (0, "0%"),
        ("0.125", "12%"),
        (1, "100%"),
    ],
)
def test_report_cells_only_present_valid_allele_fractions(frequency, expected):
    context = structural_context()
    context["report_sections_data"]["snvs"][0]["af"] = frequency
    assert sections(document(context))["snvs"]["rows"][0][2] == expected
