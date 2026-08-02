"""Tests for canonical annotation identity enrichment."""

from __future__ import annotations

from hashlib import md5

from api.domain.core.annotation_identity import (
    annotation_identity_fields,
    enrich_annotation_identity,
)


def test_small_variant_identity_keeps_all_available_representations():
    identities = annotation_identity_fields(
        variant="p.Met89Val",
        nomenclature="p",
        source={
            "hgvsc": "c.265A>G",
            "genomic": "17:76736896:T/C",
            "simple_id": "17_76736896_T_C",
        },
    )

    assert identities == {
        "hgvsp": "p.Met89Val",
        "hgvsc": "c.265A>G",
        "genomic": "17_76736896_T_C",
        "genomic_hash": md5(b"17_76736896_T_C").hexdigest(),
    }


def test_identity_enrichment_reads_nested_bulk_variant_data():
    enriched = enrich_annotation_identity(
        {
            "variant": "p.Arg248Gln",
            "nomenclature": "p",
            "variant_data": {
                "hgvsc": "c.743G>A",
                "genomic": "17:7674220:C/T",
            },
        }
    )

    assert enriched["hgvsp"] == "p.Arg248Gln"
    assert enriched["hgvsc"] == "c.743G>A"
    assert enriched["genomic"] == "17_7674220_C_T"
    assert enriched["genomic_hash"] == md5(b"17_7674220_C_T").hexdigest()


def test_structural_identity_uses_nomenclature_specific_field():
    assert annotation_identity_fields(variant="7:10-20", nomenclature="cn", source={}) == {
        "cnv": "7:10-20"
    }
    assert annotation_identity_fields(variant="EML4^ALK", nomenclature="f", source={}) == {
        "fusion": "EML4^ALK"
    }
    assert annotation_identity_fields(variant="1:100^2:200", nomenclature="t", source={}) == {
        "translocation": "1:100^2:200"
    }


def test_selected_csq_can_supply_hgvs_identifiers():
    identities = annotation_identity_fields(
        variant="17:76736896:T/C",
        nomenclature="g",
        source={
            "INFO": {
                "selected_CSQ": {
                    "HGVSp": "p.Met89Val",
                    "HGVSc": "c.265A>G",
                }
            }
        },
    )

    assert identities == {
        "hgvsp": "p.Met89Val",
        "hgvsc": "c.265A>G",
        "genomic": "17_76736896_T_C",
        "genomic_hash": md5(b"17_76736896_T_C").hexdigest(),
    }


def test_enrichment_removes_annotation_level_simple_id_aliases():
    enriched = enrich_annotation_identity(
        {
            "variant": "p.Met89Val",
            "nomenclature": "p",
            "simple_id": "17_76736896_T_C",
            "simple_id_hash": md5(b"17_76736896_T_C").hexdigest(),
        }
    )

    assert enriched["genomic"] == "17_76736896_T_C"
    assert enriched["genomic_hash"] == md5(b"17_76736896_T_C").hexdigest()
    assert "simple_id" not in enriched
    assert "simple_id_hash" not in enriched
