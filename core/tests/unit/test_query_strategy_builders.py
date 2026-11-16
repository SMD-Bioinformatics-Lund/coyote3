"""Unit tests for ASPC-driven CNV/fusion/translocation query strategy."""

from coyote.domain.dna.dna_filters import cnvtype_variant


def test_cnv_effect_filter_retains_untyped_structural_read_calls() -> None:
    cnvs = [
        {"_id": "ratio-gain", "ratio": 0.8},
        {"_id": "declared-loss", "type": "DEL"},
        {"_id": "manta-breakpoint", "ratio": None, "SR": "43,0"},
        {"_id": "unsupported", "ratio": None},
    ]

    assert [row["_id"] for row in cnvtype_variant(cnvs, ["AMP"])] == [
        "ratio-gain",
        "manta-breakpoint",
    ]
