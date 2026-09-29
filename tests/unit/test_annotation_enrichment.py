from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import mongomock
import pytest
from bson import ObjectId

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


@pytest.mark.parametrize("group", ["solid", "hematology", "demo"])
@pytest.mark.parametrize(
    "subpanel,expected", [("named", 1), ("missing", 999), ("base", 3), (None, 3), ("", 3)]
)
def test_annotation_scope_is_consistent_across_all_assay_groups(group, subpanel, expected):
    docs = [
        {"assay": group, "subpanel": scope, "class": tier, "text": str(tier)}
        for scope, tier in [("named", 1), ("base", 2), ("other", 3)]
    ]
    docs.append({"assay": "unrelated", "subpanel": "named", "class": 4, "text": "4"})
    variant = {"INFO": {"selected_CSQ": {"SYMBOL": "TP53", "HGVSp": "p.Arg1Gly"}}}
    _, classification, _, interesting = AnnotationsRepository.get_global_annotations(
        _AnnotationRepo(docs), variant, group, subpanel
    )
    assert classification["class"] == expected
    assert [annotation["class"] for annotation in interesting.values()] == (
        [] if expected == 999 else [expected]
    )


@pytest.mark.parametrize(
    "subpanel,expected", [("named", 1), ("base", 2), (None, 2), ("absent", None)]
)
def test_annotation_queries_use_latest_tier_not_later_null_text(subpanel, expected):
    collection = mongomock.MongoClient().test.annotation
    now = datetime.now(timezone.utc)
    for index, (scope, tier) in enumerate([("named", 1), ("other", 2), ("named", None)], start=1):
        collection.insert_one(
            {
                "_id": ObjectId(f"{index:024x}"),
                "time_created": now,
                "assay": "demo",
                "subpanel": scope,
                "gene": "TP53",
                "transcript": "NM_SYNTHETIC",
                "variant": "p.Arg1Gly",
                "hgvsp": "p.Arg1Gly",
                "nomenclature": "p",
                "class": tier,
                "text": "Note",
            }
        )
    repository = AnnotationsRepository(SimpleNamespace(annotations_collection=collection))
    variant = {
        "simple_id": "1-10-A-T",
        "genes": ["TP53"],
        "HGVSp": "p.Arg1Gly",
        "INFO": {"selected_CSQ": {"SYMBOL": "TP53", "HGVSp": "p.Arg1Gly"}},
    }
    transcripts = [{"Feature": "NM_SYNTHETIC", "SYMBOL": "TP53", "HGVSp": "p.Arg1Gly"}]
    classification = repository.get_global_annotations(variant, "demo", subpanel)[1]
    assert classification["class"] == (expected or 999)
    additional = repository.get_additional_classifications(variant, "demo", subpanel)
    assert [annotation["class"] for annotation in additional] == (
        [] if expected is None else [expected]
    )
    latest = repository.get_latest_transcript_classifications(
        variant, transcripts, "demo", subpanel
    )
    assert [annotation["class"] for annotation in latest.values()] == (
        [] if expected is None else [expected]
    )


@pytest.mark.parametrize(
    "subpanel,expected", [("named", 1), ("base", 2), (None, 2), ("absent", 999)]
)
def test_fusion_annotations_use_scope_and_ignore_other_groups(subpanel, expected):
    collection = mongomock.MongoClient().test.annotation
    variant = {"breakpoint1": "1:10:+", "breakpoint2": "2:20:-", "gene1": "ETV6", "gene2": "RUNX1"}
    for index, (group, scope, tier) in enumerate(
        [("demo", "named", 1), ("demo", "other", 2), ("another", "named", 3)]
    ):
        collection.insert_one(
            {
                "variant": "1:10:+^2:20:-",
                "nomenclature": "f",
                "gene1": "ETV6",
                "gene2": "RUNX1",
                "assay": group,
                "subpanel": scope,
                "class": tier,
                "text": f"tier {tier}",
                "time_created": index,
            }
        )
    repository = AnnotationsRepository(SimpleNamespace(annotations_collection=collection))
    _, classification, _, interesting = repository.get_global_annotations(variant, "demo", subpanel)
    assert classification["class"] == expected
    assert [value["class"] for value in interesting.values()] == (
        [] if expected == 999 else [expected]
    )
