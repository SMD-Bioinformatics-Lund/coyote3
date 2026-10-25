from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import mongomock
import pytest
from bson import ObjectId

from api.infra.mongo.repositories.annotations import AnnotationsRepository
from coyote3.application.interpretation.annotation_enrichment import add_alt_class

SAMPLE_CONTEXT = {"assay_id": "synthetic_assay", "environment": "production"}


@pytest.mark.parametrize(
    "scope,namespace,visible",
    [
        ({"assay_id": "another_assay", "environment": "production"}, "clinical", True),
        ({"assay_id": "synthetic_assay", "environment": "testing"}, "sandboxed", False),
    ],
)
def test_other_assay_is_reference_only_and_sandbox_is_not_visible(scope, namespace, visible):
    collection = mongomock.MongoClient().test.annotation
    collection.insert_one(
        {
            "gene": "TP53",
            "variant": "p.Arg1Gly",
            "hgvsp": "p.Arg1Gly",
            "nomenclature": "p",
            "asp_group": "solid",
            "diagnosis_id": "breast",
            "class": 1,
            "text": None,
            "asp_id": scope["assay_id"],
            "namespace": namespace,
        }
    )
    repository = AnnotationsRepository(
        SimpleNamespace(
            annotations_collection=collection,
            assay_groups_collection=collection.database.assay_groups,
        )
    )
    finding = {"INFO": {"selected_CSQ": {"SYMBOL": "TP53", "HGVSp": "p.Arg1Gly"}}}
    texts, classification, other, interesting = repository.get_global_annotations(
        finding, "solid", "breast", sample_context=SAMPLE_CONTEXT
    )
    assert classification == {"class": 999}
    assert texts == []
    assert interesting == {}
    assert len(other) == int(visible)
    if visible:
        assert other[0]["requires_retiering"] is True
        assert other[0]["effective"] is False


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
        self.adapter = SimpleNamespace(
            assay_groups_collection=mongomock.MongoClient().test.assay_groups
        )

    def get_collection(self):
        return self.collection


def test_global_annotations_treat_null_class_as_text_annotation():
    repo = _AnnotationRepo(
        [
            {
                "gene": "FLT3",
                "variant": "p.Val1Ala",
                "nomenclature": "p",
                "asp_group": "hematology",
                "diagnosis_id": "base",
                "class": None,
                "text": "review note",
                "asp_id": SAMPLE_CONTEXT["assay_id"],
                "namespace": "clinical",
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
        repo, variant, "hematology", "base", sample_context=SAMPLE_CONTEXT
    )

    assert annotations[0]["text"] == "review note"
    assert classification == {"class": 999}
    assert other == []
    assert interesting["hematology:base"]["text"] == "review note"


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
        def get_additional_classifications(_variant, _assay_group, _diagnosis, **_kwargs):
            return [{"class": None, "author": "u", "time_created": "now"}]

    variant = add_alt_class({}, "hematology", "base", annotation_repository=Repo())

    assert variant["additional_classification"] is None


@pytest.mark.parametrize("group", ["solid", "hematology", "demo"])
@pytest.mark.parametrize(
    "diagnosis,expected", [("named", 1), ("missing", 999), ("base", 2), (None, 2), ("", 2)]
)
def test_annotation_scope_is_consistent_across_all_assay_groups(group, diagnosis, expected):
    docs = [
        {
            "asp_group": group,
            "diagnosis_id": scope,
            "class": tier,
            "asp_id": SAMPLE_CONTEXT["assay_id"],
            "namespace": "clinical",
        }
        for scope, tier in [("named", 1), ("base", 2), ("other", 3)]
    ]
    docs.append({"asp_group": "unrelated", "diagnosis_id": "named", "class": 4, "text": "4"})
    variant = {"INFO": {"selected_CSQ": {"SYMBOL": "TP53", "HGVSp": "p.Arg1Gly"}}}
    _, classification, _, interesting = AnnotationsRepository.get_global_annotations(
        _AnnotationRepo(docs), variant, group, diagnosis, sample_context=SAMPLE_CONTEXT
    )
    assert classification["class"] == expected
    assert interesting == {}


@pytest.mark.parametrize(
    "diagnosis,expected", [("named", 1), ("base", None), (None, None), ("absent", None)]
)
def test_annotation_queries_use_latest_tier_not_later_null_text(diagnosis, expected):
    collection = mongomock.MongoClient().test.annotation
    now = datetime.now(timezone.utc)
    for index, (scope, tier) in enumerate([("named", 1), ("other", 2), ("named", None)], start=1):
        collection.insert_one(
            {
                "_id": ObjectId(f"{index:024x}"),
                "time_created": now,
                "asp_group": "demo",
                "diagnosis_id": scope,
                "gene": "TP53",
                "transcript": "NM_SYNTHETIC",
                "variant": "p.Arg1Gly",
                "hgvsp": "p.Arg1Gly",
                "nomenclature": "p",
                "class": tier,
                "text": "Note" if tier is None else None,
                "asp_id": SAMPLE_CONTEXT["assay_id"],
                "namespace": "clinical",
            }
        )
    repository = AnnotationsRepository(
        SimpleNamespace(
            annotations_collection=collection,
            assay_groups_collection=collection.database.assay_groups,
        )
    )
    variant = {
        "simple_id": "1-10-A-T",
        "genes": ["TP53"],
        "HGVSp": "p.Arg1Gly",
        "INFO": {"selected_CSQ": {"SYMBOL": "TP53", "HGVSp": "p.Arg1Gly"}},
    }
    transcripts = [{"Feature": "NM_SYNTHETIC", "SYMBOL": "TP53", "HGVSp": "p.Arg1Gly"}]
    classification = repository.get_global_annotations(
        variant, "demo", diagnosis, sample_context=SAMPLE_CONTEXT
    )[1]
    assert classification["class"] == (expected or 999)
    additional = repository.get_additional_classifications(
        variant, "demo", diagnosis, sample_context=SAMPLE_CONTEXT
    )
    assert [annotation["class"] for annotation in additional] == (
        [] if expected is None else [expected]
    )
    latest = repository.get_latest_transcript_classifications(
        variant, transcripts, "demo", diagnosis, sample_context=SAMPLE_CONTEXT
    )
    assert [annotation["class"] for annotation in latest.values()] == (
        [] if expected is None else [expected]
    )


@pytest.mark.parametrize(
    "diagnosis,expected", [("named", 1), ("base", 999), (None, 999), ("absent", 999)]
)
def test_fusion_annotations_use_scope_and_ignore_other_groups(diagnosis, expected):
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
                "asp_group": group,
                "diagnosis_id": scope,
                "class": tier,
                "asp_id": SAMPLE_CONTEXT["assay_id"],
                "namespace": "clinical",
                "time_created": index,
            }
        )
    repository = AnnotationsRepository(
        SimpleNamespace(
            annotations_collection=collection,
            assay_groups_collection=collection.database.assay_groups,
        )
    )
    _, classification, _, interesting = repository.get_global_annotations(
        variant, "demo", diagnosis, sample_context=SAMPLE_CONTEXT
    )
    assert classification["class"] == expected
    assert interesting == {}
