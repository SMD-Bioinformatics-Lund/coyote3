"""Unit tests for the released DNA SNV query-policy builder."""

from __future__ import annotations

import pytest

from api.config.clinical_query_policy import SNV_QUERY_POLICY, load_snv_query_policy
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


def _logical_normal_form(value: object) -> object:
    """Normalize commutative Mongo logical clauses for predicate comparison."""
    if isinstance(value, list):
        return [_logical_normal_form(item) for item in value]
    if not isinstance(value, dict):
        return value
    normalized: dict[object, object] = {}
    for key, child in value.items():
        normalized_child = _logical_normal_form(child)
        if key in {"$and", "$or", "$nor"} and isinstance(normalized_child, list):
            normalized[key] = sorted(normalized_child, key=repr)
        else:
            normalized[key] = normalized_child
    return normalized


def _settings(**overrides: object) -> dict:
    settings = {
        "id": "SAMPLE_1",
        "asp_id": "hema_gmsv1",
        "subpanel_id": "hem",
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
    settings.update(overrides)
    return settings


def test_paired_query_uses_only_selected_transcript_consequence() -> None:
    query = build_query("hematology", _settings())
    query_text = str(query)

    assert query["SAMPLE_ID"] == "SAMPLE_1"
    assert "INFO.selected_CSQ.Consequence" in query_text
    assert "INFO.CSQ" not in query_text
    assert _contains_mapping(
        query, {"INFO.selected_CSQ.Consequence": {"$in": ["missense_variant"]}}
    )


def test_paired_query_checks_every_configured_population_frequency_source() -> None:
    query = build_query("hematology", _settings())
    query_text = str(query)

    for field in SNV_QUERY_POLICY.population_frequency_fields:
        assert field in query_text
    assert _contains_mapping(query, {"GT": {"$not": {"$elemMatch": {"type": "control"}}}})


def test_generic_case_only_omits_control_but_retains_population_frequency_checks() -> None:
    query = build_query("generic_case_only", _settings())
    query_text = str(query)

    assert "'type': 'control'" not in query_text
    for field in SNV_QUERY_POLICY.population_frequency_fields:
        assert field in query_text
    assert "INFO.selected_CSQ.Consequence" in query_text


def test_unconfigured_group_uses_safe_default_paired_policy() -> None:
    query = build_query("unconfigured_group", _settings())
    query_text = str(query)

    assert "'type': 'control'" in query_text
    for field in SNV_QUERY_POLICY.population_frequency_fields:
        assert field in query_text


def test_exceptions_are_scoped_and_do_not_use_alternate_transcripts() -> None:
    hema_query = build_query("hematology", _settings())
    solid_query = build_query("solid", _settings(asp_id="solid_gmsv3", subpanel_id="colon"))

    assert _contains_mapping(hema_query, {"INFO.selected_CSQ.SYMBOL": {"$in": ["FLT3"]}})
    assert _contains_mapping(solid_query, {"INFO.selected_CSQ.SYMBOL": {"$in": ["TERT", "NFKBIE"]}})
    assert _contains_mapping(
        solid_query,
        {
            "INFO.selected_CSQ.Consequence": {
                "$in": ["regulatory_region_variant", "TF_binding_site_variant"]
            }
        },
    )
    assert "INFO.CSQ" not in str(hema_query)
    assert "INFO.CSQ" not in str(solid_query)


def test_germline_query_requires_a_typed_admission_exception() -> None:
    query = build_query("hematology", _settings(), intent="germline")

    assert _contains_mapping(query, {"INFO.MYELOID_GERMLINE": 1})
    assert _contains_mapping(query, {"INFO.selected_CSQ.SYMBOL": {"$in": ["CEBPA"]}})
    assert _contains_mapping(query, {"FILTER": {"$in": ["GERMLINE"]}})
    assert _contains_mapping(query, {"CHROM": {"$in": ["1"]}})


def test_scope_without_configured_germline_admission_matches_nothing(tmp_path) -> None:
    policy_path = tmp_path / "policy.toml"
    policy_path.write_text(
        """
[snv]
default_somatic_policy = "paired"
default_germline_policy = "exception_only"
population_frequency_fields = ["gnomad_frequency"]
""".strip(),
        encoding="utf-8",
    )
    policy = load_snv_query_policy(policy_path)

    query = build_query("hematology", _settings(), intent="germline", policy=policy)

    assert _contains_mapping(query, {"_id": {"$exists": False}})


def test_policy_rejects_unsupported_query_keys(tmp_path) -> None:
    policy_path = tmp_path / "policy.toml"
    policy_path.write_text(
        """
[snv]
default_somatic_policy = "paired"
default_germline_policy = "exception_only"
population_frequency_fields = ["gnomad_frequency"]
unrecognized = true
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="unsupported key"):
        load_snv_query_policy(policy_path)


def test_policy_rejects_query_exception_priority(tmp_path) -> None:
    policy_path = tmp_path / "policy.toml"
    policy_path.write_text(
        """
[snv]
default_somatic_policy = "paired"
default_germline_policy = "exception_only"
population_frequency_fields = ["gnomad_frequency"]

[[snv.exceptions]]
id = "deprecated_priority"
priority = 1
mode = "admit"
genes = ["TP53"]
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="unsupported key"):
        load_snv_query_policy(policy_path)


def test_exclusion_exception_removes_matching_findings_after_baseline(tmp_path) -> None:
    policy_path = tmp_path / "policy.toml"
    policy_path.write_text(
        """
[snv]
default_somatic_policy = "paired"
default_germline_policy = "exception_only"
population_frequency_fields = ["gnomad_frequency"]

[[snv.exceptions]]
id = "exclude_low_quality_tert"
mode = "exclude"
intents = ["somatic"]
assay_groups = ["solid"]
genes = ["TERT"]
filter_values = ["LOWQUAL"]
""".strip(),
        encoding="utf-8",
    )
    policy = load_snv_query_policy(policy_path)

    query = build_query("solid", _settings(), policy=policy)

    assert _contains_mapping(
        query,
        {
            "$nor": [
                {
                    "$and": [
                        {"INFO.selected_CSQ.SYMBOL": {"$in": ["TERT"]}},
                        {"FILTER": {"$in": ["LOWQUAL"]}},
                    ]
                }
            ]
        },
    )


def test_equivalent_exception_block_order_produces_the_same_query(tmp_path) -> None:
    policy_template = """
[snv]
default_somatic_policy = "paired"
default_germline_policy = "exception_only"
population_frequency_fields = ["gnomad_frequency"]

{exceptions}
""".strip()
    first_exception = """
[[snv.exceptions]]
id = "alpha"
mode = "extend_consequence"
genes = ["ASXL1"]
""".strip()
    second_exception = """
[[snv.exceptions]]
id = "beta"
mode = "extend_consequence"
genes = ["TP53"]
""".strip()
    first_path = tmp_path / "first.toml"
    second_path = tmp_path / "second.toml"
    first_path.write_text(
        policy_template.format(exceptions=f"{first_exception}\n\n{second_exception}"),
        encoding="utf-8",
    )
    second_path.write_text(
        policy_template.format(exceptions=f"{second_exception}\n\n{first_exception}"),
        encoding="utf-8",
    )

    first_query = build_query("hematology", _settings(), policy=load_snv_query_policy(first_path))
    second_query = build_query("hematology", _settings(), policy=load_snv_query_policy(second_path))

    assert _logical_normal_form(first_query) == _logical_normal_form(second_query)


def test_clinical_consequence_groups_resolve_from_versioned_metadata_groups() -> None:
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

    assert terms == [
        "splice_donor_variant",
        "frameshift_variant",
        "inframe_deletion",
        "missense_variant",
        "coding_sequence_variant",
    ]
