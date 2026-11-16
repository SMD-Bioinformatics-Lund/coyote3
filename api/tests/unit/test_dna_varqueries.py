"""Unit tests for the released DNA SNV query-policy builder."""

from __future__ import annotations

from dataclasses import replace

from api_test_support.query_settings import _settings
from coyote.config.clinical_query_policy import CLINICAL_QUERY_POLICY, load_clinical_query_policy
from coyote.domain.dna.varqueries import build_query
from coyote_api.bootstrap.paths import CLINICAL_QUERY_SEED_PATH
from coyote_mongo.selection import compile_selection

SNV_QUERY_POLICY = CLINICAL_QUERY_POLICY.snv


def _load_snv_policy(path):
    """Complete focused SNV fixtures with the other required analysis namespaces."""
    text = path.read_text(encoding="utf-8")
    path.write_text(
        f"{text}\n\n[cnv]\n\n[translocation]\n\n[fusion]\n\n[pgx]\n",
        encoding="utf-8",
    )
    return load_clinical_query_policy(path).snv


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


def test_paired_query_uses_aggregated_transcript_consequence_terms() -> None:
    query = compile_selection(build_query("hematology", _settings()))
    query_text = str(query)

    assert query["SAMPLE_ID"] == "SAMPLE_1"
    assert "consequence_terms" in query_text
    assert "INFO.CSQ" not in query_text
    assert _contains_mapping(query, {"consequence_terms": {"$in": ["missense_variant"]}})


def test_paired_query_checks_every_configured_population_frequency_source() -> None:
    query = compile_selection(build_query("hematology", _settings()))
    query_text = str(query)

    for field in SNV_QUERY_POLICY.population_frequency_fields:
        assert field in query_text
    assert _contains_mapping(query, {"GT": {"$not": {"$elemMatch": {"type": "control"}}}})


def test_case_only_policy_omits_control_but_retains_population_frequency_checks() -> None:
    policy = replace(SNV_QUERY_POLICY, assay_group_policies={"hematology": "case_only"})
    query = compile_selection(build_query("hematology", _settings(), policy=policy))
    query_text = str(query)

    assert "'type': 'control'" not in query_text
    for field in SNV_QUERY_POLICY.population_frequency_fields:
        assert field in query_text
    assert "consequence_terms" in query_text


def test_unconfigured_group_uses_safe_default_paired_policy() -> None:
    query = compile_selection(build_query("unconfigured_group", _settings()))
    query_text = str(query)

    assert "'type': 'control'" in query_text
    for field in SNV_QUERY_POLICY.population_frequency_fields:
        assert field in query_text


def test_exceptions_are_scoped_and_use_aggregated_consequence_terms() -> None:
    policy = load_clinical_query_policy(CLINICAL_QUERY_SEED_PATH).snv
    hema_query = compile_selection(build_query("hematology", _settings(), policy=policy))
    solid_query = compile_selection(
        build_query(
            "solid", _settings(asp_id="demo-solid_gmsv3", diagnosis_id="colon"), policy=policy
        )
    )

    assert _contains_mapping(hema_query, {"genes": {"$in": ["FLT3"]}})
    assert _contains_mapping(solid_query, {"genes": {"$in": ["TERT", "NFKBIE"]}})
    assert _contains_mapping(
        solid_query,
        {"consequence_terms": {"$in": ["regulatory_region_variant", "TF_binding_site_variant"]}},
    )
    assert "INFO.CSQ" not in str(hema_query)
    assert "INFO.CSQ" not in str(solid_query)


def test_independent_germline_query_retains_explicit_published_admission_rules() -> None:
    query = compile_selection(
        build_query(
            "hematology",
            _settings(),
            intent="germline",
            policy=load_clinical_query_policy(CLINICAL_QUERY_SEED_PATH).snv,
        )
    )

    assert _contains_mapping(query, {"INFO.MYELOID_GERMLINE": {"$eq": 1}})
    assert _contains_mapping(query, {"genes": {"$in": ["CEBPA"]}})
    assert _contains_mapping(query, {"FILTER": {"$in": ["GERMLINE"]}})
    assert _contains_mapping(query, {"CHROM": {"$in": ["1"]}})


def test_germline_scope_without_admission_rules_uses_normal_filters(tmp_path) -> None:
    policy_path = tmp_path / "policy.toml"
    policy_path.write_text(
        """
[snv]
""".strip(),
        encoding="utf-8",
    )
    policy = _load_snv_policy(policy_path)

    query = compile_selection(
        build_query("hematology", _settings(), intent="germline", policy=policy)
    )

    assert policy.policy_for(assay_group="hematology", intent="germline") == "case_only"
    assert not _contains_mapping(query, {"_id": {"$exists": False}})
    assert _contains_mapping(
        query,
        {
            "AF": {"$gte": 0.1, "$lte": 1.0},
            "DP": {"$gte": 250.0},
            "VD": {"$gte": 10.0},
        },
    )


def test_exclusion_exception_removes_matching_findings_after_baseline(tmp_path) -> None:
    policy_path = tmp_path / "policy.toml"
    policy_path.write_text(
        """
[snv]

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
    policy = _load_snv_policy(policy_path)

    query = compile_selection(build_query("solid", _settings(), policy=policy))

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

    first_query = compile_selection(
        build_query("hematology", _settings(), policy=_load_snv_policy(first_path))
    )
    second_query = compile_selection(
        build_query("hematology", _settings(), policy=_load_snv_policy(second_path))
    )

    assert _logical_normal_form(first_query) == _logical_normal_form(second_query)
