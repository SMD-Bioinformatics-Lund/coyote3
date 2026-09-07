"""Tests for canonical annotation identity enrichment."""

from __future__ import annotations

from hashlib import md5

import pytest

from api.domain.core.annotation_identity import (
    annotation_context_fields,
    annotation_identity_fields,
    enrich_annotation_identity,
)
from api.domain.core.dna.dna_variants import get_variant_nomenclature
from api.infra.mongo.repositories.annotations import AnnotationsRepository


class _InsertResult:
    inserted_id = "annotation-1"


class _AnnotationCollection:
    def __init__(self) -> None:
        self.inserted: dict | None = None

    def insert_one(self, document: dict) -> _InsertResult:
        self.inserted = document
        return _InsertResult()


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


def test_identity_enrichment_uses_explicit_transient_finding_source():
    enriched = enrich_annotation_identity(
        {
            "variant": "p.Arg248Gln",
            "nomenclature": "p",
        },
        source={
            "hgvsc": "c.743G>A",
            "genomic": "17:7674220:C/T",
        },
    )

    assert enriched["hgvsp"] == "p.Arg248Gln"
    assert enriched["hgvsc"] == "c.743G>A"
    assert enriched["genomic"] == "17_7674220_C_T"
    assert enriched["genomic_hash"] == md5(b"17_7674220_C_T").hexdigest()


def test_annotation_action_requires_explicit_canonical_identity():
    assert get_variant_nomenclature({"nomenclature": "P", "variant": " p.Arg248Gln "}) == (
        "p",
        "p.Arg248Gln",
    )

    with pytest.raises(ValueError, match="nomenclature must be one of"):
        get_variant_nomenclature({"variant": "p.Arg248Gln", "var_p": "p.Arg248Gln"})
    with pytest.raises(ValueError, match="variant is required"):
        get_variant_nomenclature({"nomenclature": "p", "var_p": "p.Arg248Gln"})


def test_structural_identity_remains_in_universal_variant_field():
    assert annotation_identity_fields(variant="7:10-20", nomenclature="cn", source={}) == {}
    assert annotation_identity_fields(variant="EML4^ALK", nomenclature="f", source={}) == {}
    assert annotation_identity_fields(variant="1:100^2:200", nomenclature="t", source={}) == {}


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


def test_enrichment_keeps_only_nomenclature_specific_fields():
    enriched = enrich_annotation_identity(
        {
            "variant": "p.Val157GlyfsTer24",
            "nomenclature": "p",
            "hgvsc": "c.469_470del",
            "genomic": "17_7673800_AC_A",
            "gene": "TP53",
            "transcript": "NM_000546.6",
            "gene1": "WRONG1",
            "gene2": "WRONG2",
            "class": 1,
            "text": None,
        }
    )

    assert enriched == {
        "variant": "p.Val157GlyfsTer24",
        "nomenclature": "p",
        "hgvsp": "p.Val157GlyfsTer24",
        "hgvsc": "c.469_470del",
        "genomic": "17_7673800_AC_A",
        "genomic_hash": md5(b"17_7673800_AC_A").hexdigest(),
        "gene": "TP53",
        "transcript": "NM_000546.6",
        "class": 1,
    }


def test_enrichment_uses_structural_nomenclature_shapes():
    cnv = enrich_annotation_identity(
        {
            "variant": "7:10-20",
            "nomenclature": "cn",
            "gene": "EGFR",
            "transcript": "NM_005228.5",
            "text": "reviewed",
            "class": None,
        }
    )
    fusion = enrich_annotation_identity(
        {
            "variant": "2:10^10:20",
            "nomenclature": "f",
            "gene": "WRONG",
            "gene1": "EML4",
            "gene2": "ALK",
            "class": 2,
            "text": None,
        }
    )

    assert cnv == {
        "variant": "7:10-20",
        "nomenclature": "cn",
        "text": "reviewed",
    }
    assert fusion == {
        "variant": "2:10^10:20",
        "nomenclature": "f",
        "gene1": "EML4",
        "gene2": "ALK",
        "class": 2,
    }


def test_context_fields_follow_nomenclature_without_null_placeholders():
    source = {
        "gene": "TP53",
        "transcript": "NM_000546.6",
        "gene1": "EML4",
        "gene2": "ALK",
    }

    assert annotation_context_fields(nomenclature="p", source=source) == {
        "gene": "TP53",
        "transcript": "NM_000546.6",
    }
    assert annotation_context_fields(nomenclature="cn", source=source) == {}
    assert annotation_context_fields(nomenclature="f", source=source) == {
        "gene1": "EML4",
        "gene2": "ALK",
    }


def test_single_classification_insert_uses_the_stable_flat_identity_shape():
    collection = _AnnotationCollection()
    repository = AnnotationsRepository.__new__(AnnotationsRepository)
    repository.get_collection = lambda: collection

    repository.insert_classified_variant(
        "p.Val157GlyfsTer24",
        "p",
        1,
        {
            "assay_group": "global",
            "subpanel": "base",
            "gene": "TP53",
            "transcript": "NM_000546.6",
            "hgvsp": "p.Val157GlyfsTer24",
            "hgvsc": "c.469_470del",
            "genomic": "17_7673800_AC_A",
            "genomic_hash": md5(b"17_7673800_AC_A").hexdigest(),
        },
    )

    assert collection.inserted is not None
    assert collection.inserted["variant"] == "p.Val157GlyfsTer24"
    assert collection.inserted["hgvsp"] == "p.Val157GlyfsTer24"
    assert collection.inserted["hgvsc"] == "c.469_470del"
    assert collection.inserted["genomic"] == "17_7673800_AC_A"
    assert collection.inserted["genomic_hash"] == md5(b"17_7673800_AC_A").hexdigest()
    assert "cnv" not in collection.inserted
    assert "fusion" not in collection.inserted
    assert "translocation" not in collection.inserted
    assert collection.inserted["class"] == 1
    assert "text" not in collection.inserted
    assert "variant_data" not in collection.inserted
