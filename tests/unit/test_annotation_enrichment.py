from __future__ import annotations

from api.application.interpretation.annotation_enrichment import add_alt_class
from api.infra.mongo.repositories.annotations import AnnotationsRepository


class _Cursor(list):
    def sort(self, *_args, **_kwargs):
        return self


class _Collection:
    def __init__(self, docs):
        self.docs = docs

    def find(self, *_args, **_kwargs):
        return _Cursor(self.docs)


class _AnnotationRepo:
    def __init__(self, docs):
        self.collection = _Collection(docs)

    def get_collection(self):
        return self.collection


def test_global_annotations_treat_null_class_as_text_annotation():
    repo = _AnnotationRepo(
        [
            {
                "gene": "FLT3",
                "variant": "p.Val1Ala",
                "nomenclature": "p",
                "assay": "hematology",
                "subpanel": "base",
                "class": None,
                "text": "review note",
            }
        ]
    )
    variant = {
        "CHROM": "13",
        "POS": 28023318,
        "REF": "A",
        "ALT": "T",
        "INFO": {"selected_CSQ": {"SYMBOL": "FLT3", "HGVSp": "p.Val1Ala", "HGVSc": ""}},
    }

    annotations, classification, other, interesting = AnnotationsRepository.get_global_annotations(
        repo, variant, "hematology", "base"
    )

    assert annotations[0]["text"] == "review note"
    assert classification == {"class": 999}
    assert other == []
    assert interesting["hematology"]["text"] == "review note"


def test_global_annotations_accept_null_optional_hgvs_values():
    repo = _AnnotationRepo([])
    variant = {
        "CHROM": "13",
        "POS": 28023318,
        "REF": "A",
        "ALT": "T",
        "INFO": {"selected_CSQ": {"SYMBOL": "FLT3", "HGVSp": None, "HGVSc": None}},
    }

    annotations, classification, other, interesting = AnnotationsRepository.get_global_annotations(
        repo, variant, "hematology", "base"
    )

    assert annotations == []
    assert classification == {"class": 999}
    assert other == []
    assert interesting == {}


def test_add_alt_class_ignores_null_classification():
    class Repo:
        @staticmethod
        def get_additional_classifications(_variant, _assay_group, _subpanel):
            return [{"class": None, "author": "u", "time_created": "now"}]

    variant = add_alt_class({}, "hematology", "base", annotation_repository=Repo())

    assert variant["additional_classification"] is None
