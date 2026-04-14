"""Tests for assay/default filter merge behavior."""

from __future__ import annotations

from api.common.assay_filters import (
    format_assay_config,
    get_sample_effective_genes,
    merge_sample_settings_with_assay_config,
)
from api.contracts.managed_resources import aspc_spec_for_category
from api.contracts.managed_ui_schemas import build_form_spec
from api.contracts.schemas.dna import DnaFiltersDoc
from api.contracts.schemas.rna import RnaFiltersDoc


def test_merge_sample_settings_only_uses_assay_defaults_when_filters_missing() -> None:
    """Stored sample filters should remain authoritative once present."""
    sample = {
        "filters": {
            "vep_consequences": [],
            "cnveffects": None,
            "min_depth": None,
            "genelists": [],
        }
    }
    assay_config = {
        "filters": {
            "vep_consequences": ["splicing", "missense"],
            "cnveffects": ["gain", "loss"],
            "min_depth": 100,
            "genelists": ["hematology_myeloid"],
        }
    }

    merged = merge_sample_settings_with_assay_config(sample, assay_config)

    assert merged["filters"]["vep_consequences"] == []
    assert merged["filters"]["cnveffects"] is None
    assert merged["filters"]["min_depth"] is None
    assert merged["filters"]["genelists"] == []


def test_merge_sample_settings_uses_assay_defaults_when_filters_missing() -> None:
    """Missing sample filters should be initialized from assay defaults."""
    sample = {}
    assay_config = {
        "filters": {
            "vep_consequences": ["splicing", "missense"],
            "cnveffects": ["gain", "loss"],
            "min_depth": 100,
            "genelists": ["hematology_myeloid"],
        }
    }

    merged = merge_sample_settings_with_assay_config(sample, assay_config)

    assert merged["filters"]["vep_consequences"] == ["splicing", "missense"]
    assert merged["filters"]["cnveffects"] == ["gain", "loss"]
    assert merged["filters"]["min_depth"] == 100
    assert merged["filters"]["genelists"] == ["hematology_myeloid"]


def test_format_assay_config_excludes_meta_keys_from_filters_section() -> None:
    """Formatted ASPC filters should not carry UI/meta keys into sample filters."""
    formatted = format_assay_config(
        {
            "_id": "oid-1",
            "filters": {
                "max_freq": 1,
                "min_freq": 0.03,
                "vep_consequences": ["missense"],
            },
            "reporting": {"report_sections": ["SNV"]},
        },
        build_form_spec(aspc_spec_for_category("DNA")),
    )

    assert "_id" not in formatted["filters"]
    assert "filters" not in formatted["filters"]


def test_dna_filters_doc_restores_defaults_for_null_and_empty_values() -> None:
    """DNA filter contract should normalize null/empty values back to defaults."""
    filters = DnaFiltersDoc.model_validate(
        {
            "min_depth": None,
            "vep_consequences": [],
            "cnveffects": [],
            "small_variants_genelists": [],
        }
    )

    assert filters.min_depth == 100
    assert filters.vep_consequences == []
    assert filters.cnveffects == ["gain", "loss"]
    assert filters.genelists == []


def test_rna_filters_doc_restores_defaults_for_null_and_empty_values() -> None:
    """RNA filter contract should normalize null/empty values back to defaults."""
    filters = RnaFiltersDoc.model_validate(
        {
            "min_spanning_reads": None,
            "fusion_callers": [],
            "fusion_effects": None,
            "fusion_genelists": [],
        }
    )

    assert filters.min_spanning_reads == 0
    assert filters.fusion_callers == []
    assert filters.fusion_effects == []
    assert filters.fusion_genelists == []


def test_effective_genes_respects_adhoc_list_types_for_target() -> None:
    """Ad hoc genes should only apply to matching SNV/CNV/Fusion targets."""
    sample = {"filters": {"adhoc_genes": {"cnv": {"label": "focus", "genes": ["EGFR"]}}}}
    asp = {"covered_genes": ["TP53", "EGFR"], "asp_family": "panel"}

    _, snv_effective = get_sample_effective_genes(sample, asp, {}, target="snv")
    _, cnv_effective = get_sample_effective_genes(sample, asp, {}, target="cnv")

    assert snv_effective == []
    assert cnv_effective == ["EGFR"]


def test_effective_genes_leave_snv_unfiltered_when_no_genelists_selected() -> None:
    """SNV effective genes should stay empty until a list or ad hoc genes are selected."""
    sample = {"filters": {"genelists": []}}
    asp = {"covered_genes": ["TP53", "EGFR"], "asp_family": "panel"}

    _, snv_effective = get_sample_effective_genes(sample, asp, {}, target="snv")

    assert snv_effective == []


def test_effective_genes_fall_back_to_asp_genes_when_no_cnv_genelist_selected() -> None:
    """CNV effective genes should default to assay covered genes when no lists are selected."""
    sample = {"filters": {"cnv_genelists": []}}
    asp = {"covered_genes": ["TP53", "EGFR"], "asp_family": "panel"}

    _, cnv_effective = get_sample_effective_genes(sample, asp, {}, target="cnv")

    assert cnv_effective == ["EGFR", "TP53"]


def test_effective_genes_use_selected_cnv_genelist_when_present() -> None:
    """CNV effective genes should narrow to the selected CNV genelist when provided."""
    sample = {"filters": {"cnv_genelists": ["GL1"]}}
    asp = {"covered_genes": ["TP53", "EGFR", "MYC"], "asp_family": "panel"}
    selected_lists = {
        "GL1": {
            "displayname": "GL1",
            "is_active": True,
            "genes": ["EGFR", "MYC"],
            "adhoc": False,
        }
    }

    _, cnv_effective = get_sample_effective_genes(sample, asp, selected_lists, target="cnv")

    assert sorted(cnv_effective) == ["EGFR", "MYC"]
