"""Tests for assay/default filter merge behavior."""

from __future__ import annotations

import pytest
from coyote.domain.common.assay_filters import get_sample_effective_genes
from coyote.domain.common.sample_filters import normalize_sample_filters, snv_filter_intents
from coyote.domain.filter_profiles import DnaFilterProfilesDoc, RnaFilterProfilesDoc


@pytest.mark.parametrize(
    "intents,configuration,expected",
    [
        (["somatic", "germline"], {}, ["somatic"]),
        (["germline", "somatic"], {"snv_filter_mode": "shared"}, ["somatic"]),
        (["somatic", "germline"], {"snv_filter_mode": "independent"}, ["somatic", "germline"]),
        (["germline"], {}, ["germline"]),
    ],
)
def test_aspc_selects_one_shared_profile_or_enabled_independent_profiles(
    intents, configuration, expected
):
    """Flow selection does not merge or modify the persisted profile values."""
    sample = {"analysis_intents": intents}
    assert snv_filter_intents(sample, configuration) == expected
    assert sample == {"analysis_intents": intents}


def test_canonical_rna_filter_profiles_accept_fusion_descriptions() -> None:
    """Persisted RNA sample filters must accept configured description terms."""
    filters = normalize_sample_filters(
        {
            "somatic": {
                "fusion": {
                    "fusion_descriptions": ["known", "matched-normal"],
                }
            }
        },
        asp_category="rna",
        analysis_intents=["somatic"],
        canonical=True,
    )

    assert filters["somatic"]["fusion"]["fusion_descriptions"] == [
        "known",
        "matched-normal",
    ]


def test_canonical_rna_filter_profiles_normalize_fusion_caller_aliases() -> None:
    """Filter snapshots expose the same caller IDs stored on fusion calls."""
    filters = normalize_sample_filters(
        {
            "somatic": {
                "fusion": {
                    "fusion_callers": [
                        "Arriba",
                        "FusionCatcher",
                        "fusion-catcher",
                        "StarFusion",
                        "starfusion",
                    ],
                }
            }
        },
        asp_category="rna",
        analysis_intents=["somatic"],
        canonical=True,
    )

    assert filters["somatic"]["fusion"]["fusion_callers"] == [
        "arriba",
        "fusioncatcher",
        "starfusion",
    ]


def test_effective_genes_respects_adhoc_list_types_for_target() -> None:
    """Ad hoc genes should only apply to matching SNV/CNV/Fusion targets."""
    sample = {
        "filters": {
            "somatic": {
                "snv": {"snvlists": []},
                "cnv": {
                    "cnvlists": [],
                    "adhoc_genes": {"label": "focus", "genes": ["EGFR"]},
                },
            }
        }
    }
    asp = {"covered_genes": ["TP53", "EGFR"], "asp_family": "panel-dna"}

    _, snv_effective = get_sample_effective_genes(sample, asp, {}, target="snv")
    _, cnv_effective = get_sample_effective_genes(sample, asp, {}, target="cnv")

    assert snv_effective == ["EGFR", "TP53"]
    assert cnv_effective == ["EGFR"]


def test_effective_genes_use_asp_scope_when_no_snv_list_selected() -> None:
    """SNVs fall back to physical ASP coverage without an SNV selection."""
    sample = {"filters": {"somatic": {"snv": {"snvlists": []}}}}
    asp = {"covered_genes": ["TP53", "EGFR"], "asp_family": "panel-dna"}

    _, snv_effective = get_sample_effective_genes(sample, asp, {}, target="snv")

    assert snv_effective == ["EGFR", "TP53"]


def test_effective_genes_use_asp_scope_when_no_cnv_list_selected() -> None:
    """CNVs fall back to physical ASP coverage without a CNV selection."""
    sample = {"filters": {"somatic": {"cnv": {"cnvlists": []}}}}
    asp = {"covered_genes": ["TP53", "EGFR"], "asp_family": "panel-dna"}

    _, cnv_effective = get_sample_effective_genes(sample, asp, {}, target="cnv")

    assert cnv_effective == ["EGFR", "TP53"]


def test_empty_wgs_eligibility_remains_restricted() -> None:
    """An empty eligibility set must not broaden a WGS analysis to every gene."""
    sample = {"filters": {"somatic": {"snv": {"snvlists": []}}}}
    asp = {"covered_genes": [], "asp_family": "wgs"}

    covered, effective = get_sample_effective_genes(sample, asp, {}, target="snv")

    assert covered == {}
    assert effective == []


def test_effective_genes_use_selected_cnv_list_when_present() -> None:
    """CNV effective genes should narrow to the selected CNV genelist when provided."""
    sample = {"filters": {"somatic": {"cnv": {"cnvlists": ["GL1"]}}}}
    asp = {"covered_genes": ["TP53", "EGFR", "MYC"], "asp_family": "panel-dna"}
    selected_lists = {
        "GL1": {
            "displayname": "GL1",
            "is_active": True,
            "list_type": ["snv", "cnv", "fusion"],
            "genes": ["EGFR", "MYC"],
            "adhoc": False,
        }
    }

    _, cnv_effective = get_sample_effective_genes(sample, asp, selected_lists, target="cnv")

    assert sorted(cnv_effective) == ["EGFR", "MYC"]


def test_effective_genes_do_not_reuse_snv_selection_for_cnv() -> None:
    """A multi-purpose ISGL selected for SNV does not also filter CNVs."""
    sample = {
        "filters": {
            "somatic": {
                "snv": {"snvlists": ["MULTI"]},
                "cnv": {"cnvlists": []},
            }
        }
    }
    asp = {"covered_genes": ["TP53", "EGFR"], "asp_family": "panel-dna"}

    covered, cnv_effective = get_sample_effective_genes(sample, asp, {}, target="cnv")

    assert covered == {}
    assert cnv_effective == ["EGFR", "TP53"]


def test_effective_genes_reject_selected_list_not_available_for_target() -> None:
    """An ISGL unavailable for CNV cannot become the CNV gene restriction."""
    sample = {"filters": {"somatic": {"cnv": {"cnvlists": ["SNV_ONLY"]}}}}
    asp = {"covered_genes": ["TP53", "EGFR"], "asp_family": "panel-dna"}
    selected_lists = {
        "SNV_ONLY": {
            "displayname": "SNV only",
            "is_active": True,
            "list_type": ["snv"],
            "genes": ["TP53"],
            "adhoc": False,
        }
    }

    covered, cnv_effective = get_sample_effective_genes(sample, asp, selected_lists, target="cnv")

    assert covered == {}
    assert cnv_effective == []


def test_effective_genes_use_only_the_translocation_selection() -> None:
    """A multi-purpose ISGL filters translocations only when selected there."""
    sample = {
        "filters": {
            "somatic": {
                "snv": {"snvlists": ["MULTI"]},
                "translocation": {"fusionlists": ["TRANSLOC"]},
            }
        }
    }
    asp = {"covered_genes": ["TP53", "KMT2A", "NPM1"], "asp_family": "panel-dna"}
    selected_lists = {
        "TRANSLOC": {
            "displayname": "Structural targets",
            "is_active": True,
            "list_type": ["snv", "cnv", "fusion"],
            "genes": ["KMT2A"],
        }
    }

    _, genes = get_sample_effective_genes(
        sample,
        asp,
        selected_lists,
        target="translocation",
    )

    assert genes == ["KMT2A"]


def test_effective_translocation_genes_fall_back_to_asp_coverage() -> None:
    sample = {"filters": {"somatic": {"translocation": {"fusionlists": []}}}}
    asp = {"covered_genes": ["KMT2A", "NPM1"], "asp_family": "panel-dna"}

    _, genes = get_sample_effective_genes(sample, asp, {}, target="translocation")

    assert genes == ["KMT2A", "NPM1"]


def test_selected_zero_overlap_scope_remains_restrictive() -> None:
    sample = {"filters": {"somatic": {"cnv": {"cnvlists": ["OUTSIDE"]}}}}
    asp = {"covered_genes": ["TP53"], "asp_family": "panel-dna"}
    selected_lists = {
        "OUTSIDE": {
            "displayname": "Outside panel",
            "is_active": True,
            "list_type": ["cnv"],
            "genes": ["EGFR"],
        }
    }

    _, genes = get_sample_effective_genes(sample, asp, selected_lists, target="cnv")

    assert genes == []


def test_empty_wts_scope_does_not_allow_unrestricted_findings() -> None:
    sample = {
        "asp_category": "rna",
        "filters": {"somatic": {"fusion": {"fusionlists": []}}},
    }
    asp = {"covered_genes": [], "asp_family": "wts"}

    _, genes = get_sample_effective_genes(sample, asp, {}, target="fusion")
    assert genes == []


def test_canonical_profiles_preserve_explicit_empty_selections():
    """Current profiles keep intentional empty filters rather than restoring retired defaults."""
    dna = DnaFilterProfilesDoc.model_validate({"somatic": {"snv": {}, "cnv": {"cnveffects": []}}})
    assert dna.somatic.snv.min_depth == 100
    assert dna.somatic.cnv.cnveffects == []
    rna = RnaFilterProfilesDoc.model_validate({"somatic": {"fusion": {"fusion_callers": []}}})
    assert rna.somatic.fusion.min_spanning_reads == 0
    assert rna.somatic.fusion.fusion_callers == []
