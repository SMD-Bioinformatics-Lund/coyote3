"""Tests for the center-owned clinical vocabulary contract."""

from __future__ import annotations

import pytest

from api.config.assay_groups import ASP_GROUP_OPTIONS
from api.config.clinical_vocabulary import load_clinical_vocabulary


def test_current_clinical_vocabulary_loads_center_owned_options():
    """The committed center policy supplies the runtime vocabulary."""
    vocabulary = load_clinical_vocabulary()

    assert vocabulary.sample_file_keys["dna"][0] == "vcf_files"
    assert vocabulary.analysis_file_keys_by_omics["dna"]["SNV"] == ("vcf_files",)
    assert vocabulary.auth_type_options == ("local", "ldap")
    assert vocabulary.assay_families == ("panel-dna", "panel-rna", "wgs", "wts")
    assert vocabulary.default_environment == "production"


def test_assay_groups_are_software_owned_not_center_vocabulary():
    """Persistent clinical scope identifiers stay outside center TOML."""
    vocabulary = load_clinical_vocabulary()

    assert not hasattr(vocabulary, "assay_groups")
    assert ASP_GROUP_OPTIONS == (
        "hematology",
        "myeloid",
        "lymphoid",
        "solid",
        "pgx",
        "tumwgs",
        "wts",
        "fusion",
    )


def test_clinical_vocabulary_rejects_missing_center_section(tmp_path):
    """Center configuration must define each supported center-owned section."""
    config = tmp_path / "clinical_vocabulary.toml"
    config.write_text(
        """
[assay]
""",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="requires assay, environment, files, analysis, authentication, genelist, and reporting tables",
    ):
        load_clinical_vocabulary(config)


def test_clinical_vocabulary_accepts_center_defined_analysis_file_binding(tmp_path):
    """Analysis identifiers and their manifest bindings are center-owned vocabulary."""
    config = tmp_path / "clinical_vocabulary.toml"
    config.write_text(
        """
[assay]
categories = ["dna", "rna"]
families = ["panel-dna", "panel-rna"]
base_subpanel_id = "base"
[assay.family_categories]
panel-dna = "dna"
panel-rna = "rna"
[assay.family_scopes]
panel-dna = "panel"
panel-rna = "panel"

[environment]
options = ["production"]
default = "production"

[authentication]
providers = ["local", "ldap"]

[files.dna]
keys = ["variant_file"]

[files.rna]
keys = ["fusion_file"]

[files.required_by_family]
panel-dna = ["variant_file"]
panel-rna = ["fusion_file"]

[analysis.dna]
types = ["SMALL_VARIANT"]
[analysis.dna.file_keys]
SMALL_VARIANT = ["variant_file"]

[analysis.rna]
types = ["FUSION"]
[analysis.rna.file_keys]
FUSION = ["fusion_file"]

[genelist]
standard_types = ["snv"]
adhoc_types = ["adhoc_snv"]

[reporting]
required_aspc_fields = ["report_header"]

""",
        encoding="utf-8",
    )

    vocabulary = load_clinical_vocabulary(config)
    assert vocabulary.analysis_file_keys_by_omics["dna"]["SMALL_VARIANT"] == ("variant_file",)
