"""Inactive annotations retain sample history without becoming reusable interpretations."""

from datetime import datetime, timezone
from types import SimpleNamespace

import mongomock
import pytest
from bson import ObjectId

from api.infra.mongo.repositories.annotations import AnnotationsRepository
from coyote3.application.interpretation.annotation_enrichment import add_global_annotations
from coyote3.application.reporting.dna_report_payload import filter_variants_for_report
from coyote3.application.reporting.eligibility import classification_is_usable


@pytest.fixture
def repository(monkeypatch):
    """Bind annotation persistence to an isolated synthetic database."""
    db = mongomock.MongoClient().test
    repo = AnnotationsRepository(
        SimpleNamespace(
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
        "asp_id": "panel-a",
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
            "INFO": {"selected_CSQ": {"SYMBOL": "TP53", "HGVSp": "p.Arg1Gly"}},
        },
        "solid",
        "lung",
        sample_context={"assay_id": "panel-a", "environment": "production"},
    )[1]


def test_deactivation_retains_records_and_is_idempotent(repository, monkeypatch):
    """Only the selected scope/tier changes and repeating the action retains first attribution."""
    docs = [annotation(), annotation(**{"class": 1})]
    repository.get_collection().insert_many(docs)
    monkeypatch.setattr(
        "api.infra.mongo.repositories.annotations.current_username", lambda: "reviewer"
    )
    result = repository.deactivate_classified_variant(
        docs[0]["variant"],
        "p",
        docs[0],
        class_num=2,
    )
    saved = repository.get_annotation_by_oid(str(docs[0]["_id"]))
    assert result.modified_count == 1
    assert result.deleted_count == 0
    assert repository.get_collection().count_documents({}) == 2
    assert saved["is_active"] is False
    assert saved["deactivated_by"] == "reviewer"
    assert saved["class"] == 2
    assert "is_active" not in repository.get_annotation_by_oid(str(docs[1]["_id"]))
    repeated = repository.deactivate_classified_variant(
        docs[0]["variant"], "p", docs[0], class_num=2
    )
    assert repeated.modified_count == 0
    assert repository.get_annotation_by_oid(str(docs[0]["_id"])) == saved


def test_group_deactivation_includes_all_diagnoses_and_assays_but_not_other_scope(repository):
    """Group retirement includes authored text and all tiers but excludes other identities/namespaces."""
    docs = [
        annotation(),
        annotation(asp_id="panel-b", diagnosis_id="breast", **{"class": 1}),
        annotation(diagnosis_id="base", text="Stored text"),
        annotation(namespace="sandboxed"),
        annotation(asp_group="hematology"),
        annotation(gene="OTHER"),
        annotation(transcript="NM_OTHER"),
    ]
    docs[2].pop("class")
    repository.get_collection().insert_many(docs)
    result = repository.deactivate_classified_variant(docs[0]["variant"], "p", docs[0], group=True)
    assert result.modified_count == 3
    assert repository.get_collection().count_documents({"is_active": False}) == 3
    assert repository.get_collection().count_documents({}) == len(docs)
    assert all(
        repository.get_annotation_by_oid(str(doc["_id"])).get("is_active", True) for doc in docs[3:]
    )


def test_source_sample_retains_inactive_tier_when_another_sample_is_retiered(repository):
    """An inactive original assignment stays pinned while a later assignment applies elsewhere."""
    original = annotation(is_active=False, source_sample_id="original")
    current = annotation(
        source_sample_id="new",
        time_created=datetime(2026, 2, 1, tzinfo=timezone.utc),
        **{"class": 1},
    )
    repository.get_collection().insert_many([original, current])
    historical = read_classification(repository, "original")
    assert historical["_id"] == original["_id"]
    assert historical["historical_sample_match"] is True
    assert classification_is_usable(historical)
    assert read_classification(repository, "new")["_id"] == current["_id"]
    assert read_classification(repository, "unrelated")["_id"] == current["_id"]
    repository.get_collection().update_one({"_id": current["_id"]}, {"$set": {"is_active": False}})
    assert read_classification(repository, "unrelated") == {"class": 999}


@pytest.mark.parametrize("native_reference", [True, False])
def test_report_reference_preserves_exact_inactive_annotation(repository, native_reference):
    """A report link preserves a historical version instead of attaching the newest global tier."""
    sample_id = ObjectId()
    old = annotation(is_active=False)
    newest = annotation(time_created=datetime(2026, 2, 1, tzinfo=timezone.utc), **{"class": 4})
    repository.get_collection().insert_many([old, newest])
    repository.adapter.reported_variants_collection.insert_one(
        {
            "sample_oid": sample_id,
            "annotation_oid": old["_id"] if native_reference else str(old["_id"]),
        }
    )
    historical = read_classification(repository, str(sample_id))
    assert historical["_id"] == old["_id"]
    assert historical["historical_sample_match"] is True
    assert read_classification(repository, "unrelated")["_id"] == newest["_id"]


def test_latest_inactive_legacy_version_does_not_assign_an_analysis_tier(repository):
    """Inactive legacy matches neither assign a tier nor resurrect an older active version."""
    older = annotation(**{"class": 1})
    newest = annotation(is_active=False, time_created=datetime(2026, 2, 1, tzinfo=timezone.utc))
    repository.get_collection().insert_many([older, newest])
    legacy = read_classification(repository, "legacy")
    assert legacy == {"class": 999}
    assert (
        filter_variants_for_report(
            [{"classification": legacy}],
            [],
            [1, 2, 3, 4],
        )
        == []
    )


@pytest.mark.parametrize("active", [None, True, False])
def test_analysis_enrichment_only_assigns_reusable_active_tiers(repository, active):
    """Missing lifecycle flags retain active behavior; explicit false cannot auto-select a finding."""
    document = annotation(**({} if active is None else {"is_active": active}))
    repository.get_collection().insert_one(document)
    variants, selected = add_global_annotations(
        [
            {
                "SAMPLE_ID": "new-sample",
                "INFO": {"selected_CSQ": {"SYMBOL": "TP53", "HGVSp": "p.Arg1Gly"}},
            }
        ],
        "solid",
        "lung",
        annotation_repository=repository,
        sample_context={"assay_id": "panel-a", "environment": "production"},
    )
    assert variants[0]["classification"]["class"] == (999 if active is False else 2)
    assert len(selected) == (0 if active is False else 1)
    assert variants[0]["additional_classification"] is None


def test_detail_history_uses_matching_scope_and_preserves_versions_newest_first(repository):
    """History includes inactive versions but excludes other identities and clinical scopes."""
    oldest = annotation(author="first-reviewer", text="First reasoning", **{"class": 1})
    previous = annotation(
        author="second-reviewer",
        text="Revised reasoning",
        is_active=False,
        time_created=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    current = annotation(time_created=datetime(2026, 3, 1, tzinfo=timezone.utc), **{"class": 3})
    repository.get_collection().insert_many(
        [
            current,
            oldest,
            previous,
            annotation(diagnosis_id="breast"),
            annotation(asp_id="other-panel"),
            annotation(asp_group="hematology"),
            annotation(namespace="sandboxed"),
            annotation(gene="OTHER"),
            annotation(variant="p.Other", hgvsp="p.Other"),
        ]
    )
    variant = {
        "SAMPLE_ID": "review-sample",
        "INFO": {"selected_CSQ": {"SYMBOL": "TP53", "HGVSp": "p.Arg1Gly"}},
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
    assert latest["history"][0]["is_active"] is False
    assert "history" not in read_classification(repository, "review-sample")


@pytest.mark.parametrize(
    ("active", "source_sample", "selected", "expected_tier"),
    [
        (True, None, True, 1),
        (False, "rna-sample", True, 1),
        (False, None, True, 999),
        (True, None, False, 999),
    ],
)
def test_fusion_list_and_detail_match_the_same_selected_call(
    repository, active, source_sample, selected, expected_tier
):
    """List enrichment uses the selected caller identity and retains sample-linked history."""
    record = annotation(
        nomenclature="f",
        variant="22:100^9:200",
        gene1="BCR",
        gene2="ABL1",
        is_active=active,
        source_sample_id=source_sample,
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
