"""Regression tests for stable, deduplicated clinical CSV exports."""

from __future__ import annotations

from api.application.dna.export import (
    build_cnv_export_rows,
    build_snv_export_rows,
    build_transloc_export_rows,
    join_tokens,
)
from api.application.rna.expression_analysis import RnaService


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
