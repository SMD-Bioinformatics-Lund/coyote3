"""Tests for the center-owned clinical vocabulary contract."""

from __future__ import annotations

from pathlib import Path

import pytest

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
    assert vocabulary.assay_families == ("panel-dna", "panel-rna", "wes", "wgs", "wts")
    assert vocabulary.default_environment == "production"
    assert vocabulary.transcript_selection_order[:2] == (
        "ncbi_mane_plus_clinical",
        "ensembl_mane_plus_clinical",
    )
    assert "mitelman" in vocabulary.fusion_description_important_terms
    assert "banned" in vocabulary.fusion_description_not_important_terms
    assert "short_distance" in vocabulary.fusion_description_context_terms
    assert vocabulary.analysis_types_by_family["panel-rna"] == ("FUSION", "QC")
    assert vocabulary.analysis_types_by_family["wts"] == (
        "FUSION",
        "EXPRESSION",
        "CLASSIFICATION",
        "QC",
    )


def test_wes_uses_dna_inputs_and_declared_capture_genes():
    """Exome scope retains captured-gene limits rather than whole-genome coverage."""
    from api.domain.common.assay_filters import get_genes_covered_in_panel

    vocabulary = load_clinical_vocabulary()
    assert vocabulary.assay_family_categories["wes"] == "dna"
    assert vocabulary.assay_family_scopes["wes"] == "wes"
    assert vocabulary.required_file_keys_by_family["wes"] == ("vcf_files",)
    assert set(vocabulary.analysis_types_by_family["wes"]) <= set(
        vocabulary.analysis_file_keys_by_omics["dna"]
    )
    lists = get_genes_covered_in_panel(
        {"example": {"genes": ["GENE_A", "GENE_B"]}},
        {"asp_family": "wes", "covered_genes": ["GENE_A"]},
    )
    assert lists["example"]["covered"] == ["GENE_A"]
    assert lists["example"]["uncovered"] == ["GENE_B"]


def test_assay_groups_are_database_owned_not_center_vocabulary():
    """Persistent scope choices come from the registry, not center TOML."""
    vocabulary = load_clinical_vocabulary()

    assert not hasattr(vocabulary, "assay_groups")


def test_manifest_preload_bindings_follow_configured_file_keys():
    """External manifest names resolve through the vocabulary, not ingest service literals."""
    dna = manifest_file_preload_keys("dna")
    rna = manifest_file_preload_keys("rna")

    assert dna["vcf_files"] == "snvs"
    assert dna["cnv"] == "cnvs"
    assert rna["fusion_files"] == "fusions"
    assert rna["expression_path"] == "rna_expr"
    assert non_database_manifest_file_keys("dna") == {"cnvprofile"}
    assert non_database_manifest_file_keys("rna") == set()
    assert analysis_type_for_file_key("dna", "vcf_files") == "SNV"
    assert analysis_type_for_file_key("rna", "fusion_files") == "FUSION"


@pytest.mark.parametrize(
    "section",
    ["assay", "environment", "authentication", "genelist", "files", "analysis", "reporting"],
)
def test_center_cannot_redefine_application_contracts(tmp_path, section):
    """Protected sections are rejected even if their values match release defaults."""
    source = Path("api/config/center/clinical_vocabulary.toml").read_text()
    path = tmp_path / "vocabulary.toml"
    path.write_text(source + f"\n[{section}]\n")
    with pytest.raises(RuntimeError, match="Application-owned clinical definitions"):
        load_clinical_vocabulary(path)


def test_center_cannot_replace_supported_fusion_callers(tmp_path):
    """Caller parser support cannot be declared through a center policy."""
    source = Path("api/config/center/clinical_vocabulary.toml").read_text()
    path = tmp_path / "vocabulary.toml"
    path.write_text(
        source.replace(
            "[fusion.description_terms]",
            '[fusion]\ncallers = ["invented"]\n[fusion.description_terms]',
        )
    )
    with pytest.raises(RuntimeError, match="Application-owned clinical definitions"):
        load_clinical_vocabulary(path)


def test_clinical_vocabulary_requires_center_presentation_policy(tmp_path):
    """A missing center policy fails rather than silently adopting a different one."""
    path = tmp_path / "vocabulary.toml"
    path.write_text("")
    with pytest.raises(RuntimeError, match="fusion.description_terms"):
        load_clinical_vocabulary(path)


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
