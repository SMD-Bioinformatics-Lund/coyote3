"""Canonical version identifiers used in manifests and reference lookup."""

import pytest
from coyote.contracts.database_versions import (
    canonical_vcf_header_database_version_key,
    normalize_database_versions,
    require_sample_vep_version,
    sample_vep_version,
    vep_metadata_release,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "value,expected",
    [(113, "113"), ("v113.0.0", "113"), ("V113.1", "113.1"), (None, ""), ("custom", "custom")],
)
def test_vep_release_equivalence_preserves_minor_versions(value, expected) -> None:
    assert vep_metadata_release(value) == expected


def test_database_versions_normalize_missing_values_and_vep_prefix() -> None:
    assert normalize_database_versions(None) == {}
    assert normalize_database_versions(
        {"vep": " v113.1 ", "gnomad": "n/a", "clinvar": None, "cosmic": 0}
    ) == {"vep": "113.1", "cosmic": "0"}


@pytest.mark.parametrize("value", [[], "v113", {"VEP": "113"}, {None: "113"}])
def test_invalid_version_mappings_are_rejected(value) -> None:
    with pytest.raises(ValueError):
        normalize_database_versions(value)


def test_external_header_names_normalize_to_canonical_keys() -> None:
    assert canonical_vcf_header_database_version_key(" HGMD-Public ") == "hgmd_public"
    assert canonical_vcf_header_database_version_key("unknown") is None


def test_sample_version_lookup_has_no_reference_fallback() -> None:
    assert require_sample_vep_version({"database_versions": {"vep": "v113"}}) == "113"
    assert sample_vep_version({"database_versions": []}) is None
    assert sample_vep_version({"database_versions": {"vep": None}}) is None
    with pytest.raises(ValueError, match="required"):
        require_sample_vep_version({})
