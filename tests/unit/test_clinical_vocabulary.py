"""Tests for the center-owned clinical vocabulary contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from api.config.assay_groups import ASP_GROUP_OPTIONS
from api.config.clinical_vocabulary import CLINICAL_VOCABULARY, load_clinical_vocabulary
from api.config.constants import (
    analysis_type_for_file_key,
    manifest_file_preload_keys,
    non_database_manifest_file_keys,
)


def test_current_clinical_vocabulary_loads_center_owned_options():
    """The committed center policy supplies the runtime vocabulary."""
    vocabulary = load_clinical_vocabulary()

    assert vocabulary.sample_file_keys["dna"][0] == "vcf_files"
    assert vocabulary.analysis_file_keys_by_omics["dna"]["SNV"] == ("vcf_files",)
    assert vocabulary.auth_type_options == ("local", "ldap")
    assert vocabulary.assay_families == ("panel-dna", "panel-rna", "wgs", "wts")
    assert vocabulary.default_environment == "production"
    assert vocabulary.transcript_selection_order[:2] == (
        "ncbi_mane_plus_clinical",
        "ensembl_mane_plus_clinical",
    )
    assert "mitelman" in vocabulary.fusion_description_important_terms
    assert "banned" in vocabulary.fusion_description_not_important_terms
    assert "short_distance" in vocabulary.fusion_description_context_terms
    assert vocabulary.analysis_types_by_family["panel-rna"] == ("FUSION", "QC", "PGX")
    assert vocabulary.analysis_types_by_family["wts"] == (
        "FUSION",
        "EXPRESSION",
        "CLASSIFICATION",
        "QC",
        "PGX",
    )


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


def test_manifest_preload_bindings_follow_configured_file_keys():
    """External manifest names resolve through the vocabulary, not ingest service literals."""
    dna = manifest_file_preload_keys("dna")
    rna = manifest_file_preload_keys("rna")

    assert dna["vcf_files"] == "snvs"
    assert dna["cnv"] == "cnvs"
    assert rna["fusion_files"] == "fusions"
    assert rna["expression_path"] == "rna_expr"
    assert non_database_manifest_file_keys("dna") == {"cnvprofile", "pgx"}
    assert non_database_manifest_file_keys("rna") == {"pgx"}
    assert analysis_type_for_file_key("dna", "vcf_files") == "SNV"
    assert analysis_type_for_file_key("rna", "fusion_files") == "FUSION"


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
        match=(
            "requires assay, environment, files, analysis, authentication, genelist, "
            "reporting, and fusion tables"
        ),
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

[analysis.allowed_by_family]
panel-dna = ["SMALL_VARIANT"]
panel-rna = ["FUSION"]

[genelist]
standard_types = ["snv"]
adhoc_types = ["adhoc_snv"]

[reporting]
required_aspc_fields = ["report_header"]
transcript_selection_order = [
  "ncbi_mane_plus_clinical",
  "ensembl_mane_plus_clinical",
  "ncbi_mane_select",
  "ensembl_mane_select",
  "vep_canonical_protein_coding",
  "first_protein_coding",
  "first_available",
]

[fusion]
callers = ["arriba", "fusioncatcher", "starfusion"]

[fusion.description_terms]
important = ["known"]
not_important = ["banned"]
context = ["short_distance"]

""",
        encoding="utf-8",
    )

    vocabulary = load_clinical_vocabulary(config)
    assert vocabulary.analysis_file_keys_by_omics["dna"]["SMALL_VARIANT"] == ("variant_file",)
    assert vocabulary.fusion_callers == ("arriba", "fusioncatcher", "starfusion")
    assert vocabulary.fusion_annotation_metadata() == {
        "important": ["known"],
        "not_important": ["banned"],
        "context": ["short_distance"],
    }


def test_fusion_caller_aliases_resolve_to_configured_database_keys() -> None:
    """Display labels and legacy form keys must resolve to stored caller IDs."""
    assert CLINICAL_VOCABULARY.normalize_fusion_callers(
        ["FusionCatcher", "fusion-catcher", "fusioncaller_STAR_FUSION", "Arriba"]
    ) == ["fusioncatcher", "starfusion", "arriba"]

    with pytest.raises(ValueError, match="unknown value"):
        CLINICAL_VOCABULARY.normalize_fusion_callers(["unconfigured-caller"])


def test_clinical_vocabulary_rejects_overlapping_fusion_description_terms(tmp_path):
    """Each fusion annotation term must have one unambiguous visual meaning."""
    source = Path("api/config/center/clinical_vocabulary.toml").read_text(encoding="utf-8")
    source = source.replace('  "distance100kbp",', '  "mitelman",\n  "distance100kbp",')
    config = tmp_path / "clinical_vocabulary.toml"
    config.write_text(source, encoding="utf-8")

    with pytest.raises(RuntimeError, match="categories must not overlap"):
        load_clinical_vocabulary(config)
