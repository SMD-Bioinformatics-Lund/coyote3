"""Unit tests for DNA SNV query builder behavior."""

from api.core.dna.varqueries import build_query


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
    assert any(
        isinstance(item, dict)
        and "$or" in item
        and any(branch.get("INFO.MYELOID_GERMLINE") == 1 for branch in item["$or"])
        for item in outer_or
    )
    assert any(
        isinstance(item, dict) and item.get("FILTER") == {"$in": ["GERMLINE"]}
        for item in solid_outer_or
    )


def test_build_query_supports_generic_somatic_and_germline_groups() -> None:
    germline_query = build_query("generic_germline", _settings())
    somatic_query = build_query("generic_somatic", _settings())

    germline_outer = next(
        item["$or"] for item in germline_query["$and"] if isinstance(item, dict) and "$or" in item
    )
    somatic_outer = next(
        item["$and"] for item in somatic_query["$and"] if isinstance(item, dict) and "$and" in item
    )

    assert any(
        isinstance(item, dict) and item.get("INFO.MYELOID_GERMLINE") == 1 for item in germline_outer
    )
    assert any(
        isinstance(item, dict) and item.get("FILTER") == {"$in": ["GERMLINE"]}
        for item in germline_outer
    )
    assert any(isinstance(item, dict) and "GT" in item for item in somatic_outer)
    assert any(
        isinstance(item, dict)
        and "$or" in item
        and any("gnomad_frequency" in branch for branch in item["$or"])
        for item in somatic_outer
    )
