"""Tests for canonical annotation identity enrichment."""

from __future__ import annotations

from coyote.domain.dna.variant_identity import build_simple_id_hash_from_simple_id
from coyote_mongo.repositories.annotations import AnnotationsRepository


class _InsertResult:
    inserted_id = "annotation-1"


class _AnnotationCollection:
    def __init__(self) -> None:
        self.inserted: dict | None = None

    def insert_one(self, document: dict) -> _InsertResult:
        self.inserted = document
        return _InsertResult()


def test_single_classification_insert_uses_the_stable_flat_identity_shape():
    collection = _AnnotationCollection()
    repository = AnnotationsRepository.__new__(AnnotationsRepository)
    repository.get_collection = lambda: collection

    repository.insert_classified_variant(
        "p.Val157GlyfsTer24",
        "p",
        1,
        {
            "asp_group": "hematology",
            "diagnosis_id": "base",
            "asp_id": "demo-panel",
            "namespace": "clinical",
            "gene": "TP53",
            "transcript": "NM_000546.6",
            "hgvsp": "p.Val157GlyfsTer24",
            "hgvsc": "c.469_470del",
            "genomic": "17_7673800_AC_A",
            "genomic_hash": build_simple_id_hash_from_simple_id("17_7673800_AC_A"),
        },
    )

    assert collection.inserted is not None
    assert collection.inserted["variant"] == "p.Val157GlyfsTer24"
    assert collection.inserted["hgvsp"] == "p.Val157GlyfsTer24"
    assert collection.inserted["hgvsc"] == "c.469_470del"
    assert collection.inserted["genomic"] == "17_7673800_AC_A"
    assert collection.inserted["genomic_hash"] == build_simple_id_hash_from_simple_id(
        "17_7673800_AC_A"
    )
    assert "cnv" not in collection.inserted
    assert "fusion" not in collection.inserted
    assert "translocation" not in collection.inserted
    assert collection.inserted["class"] == 1
    assert "text" not in collection.inserted
    assert "variant_data" not in collection.inserted
