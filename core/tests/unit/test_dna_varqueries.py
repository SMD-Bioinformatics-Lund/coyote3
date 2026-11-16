"""Unit tests for the released DNA SNV query-policy builder."""

from __future__ import annotations

from dataclasses import asdict, replace

import pytest
from coyote.config.clinical_query_policy import load_clinical_query_policy
from coyote.domain.dna.dna_filters import get_filter_conseq_terms


def _load_snv_policy(path):
    """Complete focused SNV fixtures with the other required analysis namespaces."""
    text = path.read_text(encoding="utf-8")
    path.write_text(
        f"{text}\n\n[cnv]\n\n[translocation]\n\n[fusion]\n\n[pgx]\n",
        encoding="utf-8",
    )
    return load_clinical_query_policy(path).snv


@pytest.mark.parametrize("analysis", ["snv", "cnv", "translocation", "fusion", "pgx"])
def test_exception_scope_and_mode_preserve_order_for_every_finding_type(tmp_path, analysis):
    """Rules require every declared scope, while unrestricted rules retain their order."""
    source = "\n".join(f"[{name}]" for name in ("snv", "cnv", "translocation", "fusion", "pgx"))
    source += f"""
[[{analysis}.exceptions]]
id = "scoped"
mode = "admit"
intents = ["somatic"]
assay_groups = ["hematology"]
asp_ids = ["synthetic"]
diagnosis_ids = ["base"]
genes = ["TP53"]

[[{analysis}.exceptions]]
id = "unrestricted"
mode = "admit"
genes = ["TP53"]

[[{analysis}.exceptions]]
id = "excluded"
mode = "exclude"
genes = ["TP53"]
"""
    path = tmp_path / "policy.toml"
    path.write_text(source)
    policy = getattr(load_clinical_query_policy(path), analysis)
    scope = dict(
        assay_group="hematology", asp_id="synthetic", diagnosis_id="base", intent="somatic"
    )
    before = asdict(policy)
    assert [rule.rule_id for rule in policy.exceptions_for(**scope, mode="admit")] == [
        "scoped",
        "unrestricted",
    ]
    for field in scope:
        changed = {**scope, field: "different"}
        assert [rule.rule_id for rule in policy.exceptions_for(**changed, mode="admit")] == [
            "unrestricted"
        ]
    assert [rule.rule_id for rule in policy.exceptions_for(**scope, mode="exclude")] == ["excluded"]
    assert replace(policy, exceptions=()).exceptions_for(**scope, mode="admit") == ()
    assert asdict(policy) == before


def test_policy_rejects_unsupported_query_keys(tmp_path) -> None:
    policy_path = tmp_path / "policy.toml"
    policy_path.write_text(
        """
[snv]
unrecognized = true
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="unsupported key"):
        _load_snv_policy(policy_path)


def test_policy_rejects_query_exception_priority(tmp_path) -> None:
    policy_path = tmp_path / "policy.toml"
    policy_path.write_text(
        """
[snv]

[[snv.exceptions]]
id = "deprecated_priority"
priority = 1
mode = "admit"
genes = ["TP53"]
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="unsupported key"):
        _load_snv_policy(policy_path)


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


def test_complete_policy_requires_every_analysis_namespace(tmp_path) -> None:
    policy_path = tmp_path / "policy.toml"
    policy_path.write_text(
        """
[snv]
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="missing required block"):
        load_clinical_query_policy(policy_path)


def test_analysis_namespace_rejects_keys_from_another_finding_type(tmp_path) -> None:
    policy_path = tmp_path / "policy.toml"
    policy_path.write_text(
        """
[snv]
[cnv]
[[cnv.exceptions]]
id = "invalid_cnv_rule"
mode = "admit"
consequence_terms = ["missense_variant"]
[translocation]
[fusion]
[pgx]
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="unsupported key.*consequence_terms"):
        load_clinical_query_policy(policy_path)


def test_pgx_policy_has_its_own_typed_vocabulary(tmp_path) -> None:
    policy_path = tmp_path / "policy.toml"
    policy_path.write_text(
        """
[snv]
[cnv]
[translocation]
[fusion]
[pgx]
[[pgx.exceptions]]
id = "retain_cyp2c19"
mode = "admit"
genes = ["CYP2C19"]
diplotypes = ["*1/*2"]
""".strip(),
        encoding="utf-8",
    )

    policy = load_clinical_query_policy(policy_path)

    assert policy.pgx.exceptions[0].criteria == {
        "diplotypes": ("*1/*2",),
        "genes": ("CYP2C19",),
        "medications": (),
        "phenotypes": (),
    }


@pytest.mark.parametrize(
    "key,value",
    [
        ("default_somatic_policy", '"case_only"'),
        ("default_germline_policy", '"paired"'),
        ("population_frequency_fields", "[]"),
    ],
)
def test_center_cannot_override_query_baseline(tmp_path, key, value):
    """Center exceptions cannot replace baseline evidence definitions."""
    path = tmp_path / "policy.toml"
    path.write_text(f"[snv]\n{key} = {value}\n[cnv]\n[translocation]\n[fusion]\n[pgx]\n")
    with pytest.raises(RuntimeError, match="Application-owned query defaults"):
        load_clinical_query_policy(path)
