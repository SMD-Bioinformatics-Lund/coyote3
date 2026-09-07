"""Behavior tests for immutable clinical filter helper functions."""

from api.domain.core.filter_capabilities import (
    filter_keys,
    filter_section_for_analysis,
    select_filter_values,
)
from api.domain.core.rna.helpers import (
    create_fusioncallers,
    create_fusioneffectlist,
    get_fusion_callers,
    get_selected_fusioncall,
)


def test_fusion_filter_values_are_normalized_without_unknown_values() -> None:
    """RNA filter input accepts documented aliases and discards unknown labels."""
    assert create_fusioneffectlist(["inframe", "in-frame", "OUTFRAME", None, "unsupported"]) == [
        "in-frame",
        "out-of-frame",
    ]
    assert create_fusioncallers(
        [
            "fusioncaller_arriba",
            "Fusion-Catcher",
            "star_fusion",
            "arriba",
            None,
            "unknown",
        ]
    ) == ["arriba", "fusioncatcher", "starfusion"]


def test_fusion_call_helpers_preserve_selected_call_and_unique_callers() -> None:
    """A selected fusion call remains identifiable independently of caller order."""
    fusion = {
        "calls": [
            {"caller": "arriba", "selected": 0},
            {"caller": "starfusion", "selected": 1},
            {"caller": "arriba", "selected": 0},
        ]
    }

    assert get_selected_fusioncall(fusion) == {"caller": "starfusion", "selected": 1}
    assert set(get_fusion_callers(fusion)) == {"arriba", "starfusion"}
    assert get_selected_fusioncall({"calls": []}) is None


def test_filter_capabilities_expose_only_supported_profiles_and_keys() -> None:
    """Filter profiles reject unsupported modality, intent, and arbitrary fields."""
    assert filter_section_for_analysis(omics_layer="DNA", analysis_type="snv") == "snv"
    assert filter_section_for_analysis(omics_layer="rna", analysis_type="CNV") is None

    germline_keys = filter_keys(omics_layer="dna", intent="germline", section="snv")
    assert "min_depth" in germline_keys
    assert filter_keys(omics_layer="rna", intent="germline", section="fusion") == frozenset()

    assert select_filter_values(
        {"min_depth": 50, "min_alt_reads": 5, "arbitrary_mongo_query": {"$where": "x"}},
        omics_layer="dna",
        intent="germline",
        section="snv",
    ) == {"min_depth": 50, "min_alt_reads": 5}
