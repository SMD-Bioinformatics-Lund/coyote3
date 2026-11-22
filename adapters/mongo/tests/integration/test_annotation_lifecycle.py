"""Immutable annotations retain earlier records and saved report references."""

from datetime import datetime, timezone
from types import SimpleNamespace

import mongomock
import pytest
from bson import ObjectId
from coyote.application.interpretation.annotation_enrichment import add_global_annotations
from coyote_mongo.repositories.annotations import AnnotationsRepository
from mongo_test_support.settings import mongo_runtime


@pytest.fixture
def repository(monkeypatch):
    """Bind annotation persistence to an isolated synthetic database."""
    db = mongomock.MongoClient().test
    repo = AnnotationsRepository(
        SimpleNamespace(
            app=mongo_runtime(),
            annotations_collection=db.annotations,
            assay_groups_collection=db.groups,
            reported_variants_collection=db.reported,
        )
    )
    monkeypatch.setattr(repo, "update_many_atomic", db.annotations.update_many)
    monkeypatch.setattr(repo, "invalidate_dashboard_metrics", lambda: None)
    return repo


def annotation(**changes):
    """Build a synthetic exact-scope interpretation with stable finding identity."""
    return {
        "_id": ObjectId(),
        "variant": "p.Arg1Gly",
        "nomenclature": "p",
        "gene": "TP53",
        "hgvsp": "p.Arg1Gly",
        "transcript": "NM_1",
        "asp_group": "solid",
        "diagnosis_id": "lung",
        "namespace": "clinical",
        "class": 2,
        "time_created": datetime(2026, 1, 1, tzinfo=timezone.utc),
        **changes,
    }


def read_classification(repository, sample_id):
    """Read the effective classification for one sample and exact finding scope."""
    return repository.get_global_annotations(
        {
            "SAMPLE_ID": sample_id,
            "INFO": {"selected_CSQ": {"SYMBOL": "TP53", "HGVSp": "p.Arg1Gly", "Feature": "NM_1"}},
        },
        "solid",
        "lung",
        sample_context={"assay_id": "panel-a", "environment": "production"},
    )[1]


def test_recreating_annotation_preserves_original_and_uses_latest(repository, monkeypatch):
    old = annotation()
    repository.get_collection().insert_one(old)
    original = repository.get_annotation_by_oid(str(old["_id"]))
    monkeypatch.setattr(
        repository, "write", lambda collection, method, doc: collection.insert_one(doc)
    )
    context = {**old, "hgvsc": None, "genomic": None, "genomic_hash": None}
    repository.insert_classified_variant(old["variant"], "p", 1, context)
    assert repository.get_collection().count_documents({}) == 2
    assert repository.get_annotation_by_oid(str(old["_id"])) == original
    assert read_classification(repository, "new")["class"] == 1
    newest = read_classification(repository, "new")
    assert not {
        "rule_source",
        "is_active",
        "deactivated_at",
        "deactivated_by",
        "source_sample_id",
        "source_finding_id",
    }.intersection(newest)


@pytest.mark.parametrize("native_reference", [True, False])
def test_saved_report_preserves_original_after_new_annotation(repository, native_reference):
    sample_id = ObjectId()
    old = annotation()
    newest = annotation(time_created=datetime(2026, 2, 1, tzinfo=timezone.utc), **{"class": 4})
    repository.get_collection().insert_many([old, newest])
    repository.adapter.reported_variants_collection.insert_one(
        {
            "sample_oid": sample_id,
            "annotation_oid": old["_id"] if native_reference else str(old["_id"]),
        }
    )
    assert read_classification(repository, str(sample_id))["_id"] == old["_id"]
    assert read_classification(repository, "other")["_id"] == newest["_id"]


def test_detail_history_uses_matching_scope_and_preserves_versions_newest_first(repository):
    """History includes previous versions but excludes other identities and clinical scopes."""
    oldest = annotation(author="first-reviewer", text="First reasoning", **{"class": 1})
    previous = annotation(
        author="second-reviewer",
        text="Revised reasoning",
        time_created=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    current = annotation(time_created=datetime(2026, 3, 1, tzinfo=timezone.utc), **{"class": 3})
    repository.get_collection().insert_many(
        [
            current,
            oldest,
            previous,
            annotation(diagnosis_id="breast"),
            annotation(asp_group="hematology"),
            annotation(namespace="sandboxed"),
            annotation(gene="OTHER"),
            annotation(variant="p.Other", hgvsp="p.Other"),
        ]
    )
    variant = {
        "SAMPLE_ID": "review-sample",
        "INFO": {"selected_CSQ": {"SYMBOL": "TP53", "HGVSp": "p.Arg1Gly", "Feature": "NM_1"}},
    }
    _, latest, _, _ = repository.get_global_annotations(
        variant,
        "solid",
        "lung",
        sample_context={"assay_id": "panel-a", "environment": "production"},
        include_history=True,
    )
    assert latest["_id"] == current["_id"]
    assert [row["_id"] for row in latest["history"]] == [previous["_id"], oldest["_id"]]
    assert latest["history"][0]["author"] == "second-reviewer"
    assert latest["history"][0]["text"] == "Revised reasoning"
    assert "history" not in read_classification(repository, "review-sample")


@pytest.mark.parametrize("selected,expected_tier", [(True, 1), (False, 999)])
def test_fusion_list_and_detail_match_the_same_selected_call(repository, selected, expected_tier):
    """List enrichment uses the selected caller identity and matches the immutable annotation."""
    record = annotation(
        nomenclature="f",
        variant="22:100^9:200",
        gene1="BCR",
        gene2="ABL1",
        **{"class": 1},
    )
    repository.get_collection().insert_one(record)
    selected_call = {
        "selected": selected,
        "gene1": "BCR",
        "gene2": "ABL1",
        "breakpoint1": "22:100",
        "breakpoint2": "9:200",
    }
    fusion = {
        "_id": "fusion-1",
        "SAMPLE_ID": "rna-sample",
        "calls": [
            {"selected": False, "breakpoint1": "22:999", "breakpoint2": "9:999"},
            selected_call,
        ],
    }
    context = {"assay_id": "panel-a", "environment": "production"}
    rows, tiered = add_global_annotations(
        [fusion],
        "solid",
        "lung",
        annotation_repository=repository,
        sample_context=context,
    )
    _, detail, _, _ = repository.get_global_annotations(
        {**(selected_call if selected else {}), "SAMPLE_ID": "rna-sample"},
        "solid",
        "lung",
        sample_context=context,
    )
    assert rows[0]["classification"]["class"] == detail["class"] == expected_tier
    assert len(tiered) == (0 if expected_tier == 999 else 1)
    assert rows[0]["calls"] == fusion["calls"]
    assert "breakpoint1" not in rows[0]
