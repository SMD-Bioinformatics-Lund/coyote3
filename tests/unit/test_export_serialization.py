"""Regression tests for stable, deduplicated clinical CSV exports."""

from __future__ import annotations

import pytest

from coyote3.application.dna.export import (
    build_cnv_export_rows,
    build_snv_export_rows,
    build_transloc_export_rows,
    join_tokens,
)
from coyote3.application.rna.expression_analysis import RnaService, _fusion_sort_value


@pytest.mark.parametrize(
    ("genotype", "expected"),
    [
        ({}, "- (- / -)"),
        ({"AF": None, "VD": 0, "DP": 20}, "- (0 / 20)"),
        ({"AF": 0, "VD": 0, "DP": 20}, "0.0% (0 / 20)"),
        ({"AF": 0.25, "VD": 5}, "25.0% (5 / -)"),
        ({"AF": float("nan"), "VD": "", "DP": True}, "- (- / -)"),
        ({"AF": "0.25", "VD": "5", "DP": "20"}, "25.0% (5 / 20)"),
    ],
)
def test_snv_export_preserves_partial_genotype_measurements(genotype, expected):
    """Missing evidence is not zero and does not obscure available measurements."""
    row = build_snv_export_rows([{"GT": [{"type": "case", **genotype}]}])[0]
    assert row.case_gt == expected


def test_fusion_read_support_sort_retains_measured_zero() -> None:
    """Sorting must use the displayed zero count rather than fallback evidence."""
    row = {
        "fusion": [{"spanpairs": 0, "spanreads": 0}],
        "supporting_reads": {"span": 100, "split": 50},
    }
    assert _fusion_sort_value(row, "spanpairs") == 0
    assert _fusion_sort_value(row, "unique_spanpairs") == 0
    row["fusion"] = [{}]
    assert _fusion_sort_value(row, "spanpairs") == 100


def test_csv_preserves_measured_zero_population_frequency():
    """Measured zero is distinct from missing population evidence."""
    assert build_snv_export_rows([{"gnomad_frequency": 0}])[0].pop_freq == "0"


@pytest.mark.parametrize("purity", ["unknown", "", None])
def test_cnv_export_retains_copy_number_without_usable_purity(purity):
    """An unavailable purity estimate must not erase the independent copy number."""
    row = build_cnv_export_rows([{"ratio": 1}], {"purity": purity}, "solid")[0]
    assert row.copy_number == "4.0 (1)"
    assert row.purity_copy_number == ""


def test_cnv_export_preserves_zero_support_before_fallback():
    """A measured zero must not be replaced by another caller's read support."""
    row = build_cnv_export_rows([{"SR": 0, "PR": "10,3"}], {}, "solid")[0]
    assert row.ref_alt_reads == "0"


def test_fusion_export_retains_selected_zero_read_support():
    """CSV evidence must match the selected caller, including measured zero."""
    service = RnaService.__new__(RnaService)
    row = service.build_fusion_export_rows(
        [
            {
                "calls": [{"selected": 1, "spanpairs": 0, "spanreads": 0}],
                "supporting_reads": {"span": 100, "split": 50},
            }
        ]
    )[0]
    assert row.spanning_pairs == "0"
    assert row.unique_spanning_reads == "0"


def test_csv_token_lists_omit_null_entries():
    """Missing values must not become the literal label None."""
    assert join_tokens([None, "PASS", ""]) == "PASS"


def test_join_tokens_deduplicates_case_insensitively_and_preserves_order() -> None:
    assert join_tokens("PASS") == "PASS"
    assert join_tokens("PASS,WARN;pass|FAIL") == "PASS | WARN | FAIL"
    assert join_tokens(["fusioncatcher", "FusionCatcher", "starfusion"]) == (
        "fusioncatcher | starfusion"
    )


def test_snv_and_translocation_exports_deduplicate_list_fields() -> None:
    snv = build_snv_export_rows(
        [
            {
                "CHROM": "7",
                "POS": 140453136,
                "REF": "A",
                "ALT": "T",
                "INFO": {
                    "selected_CSQ": {
                        "SYMBOL": "BRAF",
                        "Consequence": ["missense_variant", "missense_variant"],
                    }
                },
                "FILTER": ["PASS", "pass", "WARN"],
                "GT": [],
            }
        ]
    )[0]
    assert snv.consequence == "missense_variant"
    assert snv.flags == "PASS | WARN"

    translocation = build_transloc_export_rows(
        [
            {
                "CHROM": "9",
                "POS": 133729451,
                "ALT": "22:23632628",
                "INFO": {
                    "MANE_ANN": {
                        "Gene_Name": "ABL1&BCR",
                        "Annotation": ["gene_fusion", "gene_fusion", "frameshift_variant"],
                    }
                },
            }
        ]
    )[0]
    assert translocation.var_type == "gene_fusion | frameshift_variant"


def test_cnv_and_fusion_exports_emit_each_caller_once() -> None:
    cnv = build_cnv_export_rows(
        [
            {
                "chr": "1",
                "start": 100,
                "end": 200,
                "size": 100,
                "callers": ["manta", "MANTA", "cnvkit"],
                "genes": [],
            }
        ],
        sample={},
        assay_group="solid",
    )[0]
    assert cnv.callers == "manta | cnvkit"

    service = RnaService.__new__(RnaService)
    fusion = service.build_fusion_export_rows(
        [
            {
                "gene1": "BCR",
                "gene2": "ABL1",
                "calls": [
                    {"selected": 1, "caller": "fusioncatcher", "effect": "in-frame"},
                    {"selected": 0, "caller": "FusionCatcher"},
                    {"selected": 0, "caller": "fusioncatcher"},
                ],
            }
        ]
    )[0]
    assert fusion.callers == "fusioncatcher"
