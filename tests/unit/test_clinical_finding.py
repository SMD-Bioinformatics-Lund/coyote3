"""Tests for canonical typed clinical-finding identity helpers."""

from api.domain.core.clinical_finding import (
    finding_analysis_type,
    finding_dedup_key,
    finding_display_fields,
    finding_genes,
    finding_identity,
)


def test_snv_uses_nomenclature_specific_hgvs_identity() -> None:
    finding = {
        "nomenclature": "c",
        "gene": "TP53",
        "hgvsc": "c.524G>A",
        "hgvsp": "p.Arg175His",
        "genomic": "17_7675088_C_T",
    }

    assert finding_analysis_type(finding) == "SNV"
    assert finding_identity(finding) == "c.524G>A"
    assert finding_dedup_key(finding) == ("SNV", "c.524G>A", ("TP53",))


def test_fusion_uses_both_genes_and_event_identity() -> None:
    finding = {
        "nomenclature": "f",
        "gene1": "KMT2A",
        "gene2": "AFF1",
        "variant": "KMT2A::AFF1",
    }

    assert finding_genes(finding) == ["KMT2A", "AFF1"]
    assert finding_display_fields(finding) == {
        "analysis_type": "FUSION",
        "genes": ["KMT2A", "AFF1"],
        "identity": "KMT2A::AFF1",
    }


def test_explicit_analysis_type_precedes_fallback_fields() -> None:
    finding = {
        "analysis_type": "translocation",
        "finding_type": "variant",
        "gene": "RUNX1::RUNX1T1",
        "variant": "t(8;21)",
    }

    assert finding_analysis_type(finding) == "TRANSLOCATION"
    assert finding_genes(finding) == ["RUNX1", "RUNX1T1"]
    assert finding_identity(finding) == "t(8;21)"
