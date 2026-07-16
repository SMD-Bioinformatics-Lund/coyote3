"""Unit tests for DNA SNV query builder behavior."""

from api.domain.core.dna.dna_filters import get_filter_conseq_terms
from api.domain.core.dna.varqueries import build_query


def _contains_mapping(value: object, expected: dict) -> bool:
    if isinstance(value, dict):
        if all(value.get(key) == expected_value for key, expected_value in expected.items()):
            return True
        return any(_contains_mapping(child, expected) for child in value.values())
    if isinstance(value, list):
        return any(_contains_mapping(child, expected) for child in value)
    return False


def _settings() -> dict:
    return {
        "id": "SAMPLE_1",
        "max_freq": 1.0,
        "min_freq": 0.1,
        "max_control_freq": 0.05,
        "min_depth": 250,
        "min_alt_reads": 10,
        "max_popfreq": 0.05,
        "filter_conseq": ["missense_variant"],
        "filter_genes": [],
        "disp_pos": [],
    }


def test_build_query_has_expected_base_shape() -> None:
    query = build_query("hematology", _settings())
    assert query["SAMPLE_ID"] == "SAMPLE_1"
    assert "$and" in query


def test_build_query_uses_assay_specific_base_logic() -> None:
    query = build_query("myeloid", _settings())
    solid_query = build_query("solid", _settings())
    outer_or = next(
        item["$or"] for item in query["$and"] if isinstance(item, dict) and "$or" in item
    )
    solid_outer_or = next(
        item["$or"] for item in solid_query["$and"] if isinstance(item, dict) and "$or" in item
    )
    assert outer_or != solid_outer_or
    assert _contains_mapping(outer_or, {"INFO.MYELOID_GERMLINE": 1})
    assert _contains_mapping(solid_outer_or, {"FILTER": {"$in": ["GERMLINE"]}})
    assert _contains_mapping(solid_outer_or, {"INFO.CSQ": {"$elemMatch": {"Consequence": {"$in": ["missense_variant"]}}}})


def test_build_query_supports_generic_somatic_and_germline_groups() -> None:
    germline_query = build_query("generic_germline", _settings())
    somatic_query = build_query("generic_somatic", _settings())

    somatic_outer = next(
        item["$and"] for item in somatic_query["$and"] if isinstance(item, dict) and "$and" in item
    )

    assert _contains_mapping(germline_query, {"INFO.MYELOID_GERMLINE": 1})
    assert _contains_mapping(germline_query, {"FILTER": {"$in": ["GERMLINE"]}})
    assert any(isinstance(item, dict) and "GT" in item for item in somatic_outer)
    assert any(
        isinstance(item, dict)
        and "$or" in item
        and any("gnomad_frequency" in branch for branch in item["$or"])
        for item in somatic_outer
    )


def test_build_query_keeps_master_assay_group_aliases() -> None:
    fusion_query = build_query("fusion", _settings())
    swea_query = build_query("swea", _settings())
    gmsonco_query = build_query("gmsonco", _settings())

    assert _contains_mapping(fusion_query, {"INFO.MYELOID_GERMLINE": 1})
    assert _contains_mapping(fusion_query, {"INFO.CSQ": {"$elemMatch": {"Consequence": {"$in": ["missense_variant"]}}}})
    assert _contains_mapping(swea_query, {"INFO.CSQ": {"$elemMatch": {"Consequence": {"$in": ["missense_variant"]}}}})
    assert _contains_mapping(gmsonco_query, {"INFO.CSQ": {"$elemMatch": {"Consequence": {"$in": ["missense_variant"]}}}})
    assert not _contains_mapping(swea_query, {"gnomad_frequency": {"$exists": False}})


def test_clinical_consequence_groups_resolve_from_metadata_groups() -> None:
    terms = get_filter_conseq_terms(
        ["splicing", "frameshift", "inframe_indel", "missense", "other_coding"],
        {
            "splicing": ["splice_donor_variant"],
            "frameshift": ["frameshift_variant"],
            "inframe_indel": ["inframe_deletion"],
            "missense": ["missense_variant"],
            "other_coding": ["coding_sequence_variant"],
        },
    )

    assert "splice_donor_variant" in terms
    assert "frameshift_variant" in terms
    assert "inframe_deletion" in terms
    assert "missense_variant" in terms
    assert "coding_sequence_variant" in terms


def test_build_query_matches_master_any_transcript_consequence_behavior() -> None:
    query = build_query("generic_somatic", _settings())
    query_text = str(query)

    assert "INFO.selected_CSQ.Consequence" in query_text
    assert "INFO.CSQ" in query_text
