"""Unit tests for ASPC-driven CNV/fusion/translocation query strategy."""

from api.core.dna.cnvqueries import build_cnv_query
from api.core.rna.fusion_query_builder import build_fusion_query


def test_build_cnv_query_applies_base_guards() -> None:
    query = build_cnv_query(
        "SAMPLE_1",
        {
            "cnv_loss_cutoff": -0.3,
            "cnv_gain_cutoff": 0.3,
            "min_cnv_size": 100,
            "max_cnv_size": 10000,
            "filter_genes": ["TP53"],
        },
    )
    assert query["SAMPLE_ID"] == "SAMPLE_1"
    assert "$and" in query


def test_build_fusion_query_applies_base_filters() -> None:
    query = build_fusion_query(
        "fusion",
        {
            "id": "SAMPLE_1",
            "min_spanning_reads": 10,
            "min_spanning_pairs": 10,
            "fusion_effects": ["in-frame"],
            "fusion_callers": ["arriba"],
            "checked_fusionlists": ["FCknown"],
            "filter_genes": ["KMT2A"],
        },
    )
    assert "calls" in query
    assert "$or" in query
