"""Initial sample attribution is server-owned and recovered only from creation evidence."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from api.application.ingest.collection_writes import (
    attribute_sample_import,
    upsert_collection_document,
)
from api.application.ingest.jobs import sample_entry_source
from scripts.upgrade_from_v3.backfill_sample_ingest_provenance import plan_backfill


@pytest.mark.parametrize(
    "metadata, expected",
    [
        ({"submitted_by": "operator"}, "api"),
        ({"submitted_by": "operator", "staging_dir": "/synthetic/staged"}, "upload"),
        ({"submitted_by": "ingest-watcher"}, "watcher"),
        ({"kind": "insert_documents", "submitted_by": "operator"}, "collection_import"),
    ],
)
def test_job_entry_route_comes_from_durable_metadata(metadata, expected):
    assert sample_entry_source(metadata) == expected


def test_sample_import_replaces_forged_actor_without_mutating_input():
    document = {"ingested_by": "forged", "ingest_source": "watcher"}
    assert attribute_sample_import("samples", document, "operator") == {
        "ingested_by": "operator",
        "ingest_source": "collection_import",
    }
    assert document["ingested_by"] == "forged"
    assert attribute_sample_import("variants", document, "operator") is document


@pytest.mark.parametrize("existing", [None, {}, {"ingested_by": "first", "ingest_source": "api"}])
def test_sample_replacement_preserves_initial_attribution(monkeypatch, existing):
    collection = Mock()
    collection.find_one.return_value = existing
    collection.replace_one.return_value = SimpleNamespace(
        matched_count=1, modified_count=1, upserted_id=None
    )
    monkeypatch.setattr(
        "api.application.ingest.collection_writes.normalize_collection_document",
        lambda name, document: document,
    )
    upsert_collection_document(
        SimpleNamespace(_collection=lambda name: collection),
        collection="samples",
        match={"name": "synthetic"},
        document={"ingested_by": "forged"},
        ingested_by="operator",
        upsert=True,
    )
    written = collection.replace_one.call_args.kwargs["replacement"]
    assert written["ingested_by"] == (
        "operator" if existing is None else existing.get("ingested_by")
    )
    assert written["ingest_source"] == (
        "collection_import" if existing is None else existing.get("ingest_source")
    )


def test_backfill_uses_only_successful_creation_jobs_and_preserves_known_values():
    samples = [
        {"_id": "recover"},
        {"_id": "unknown"},
        {"_id": "known", "ingested_by": "original", "ingest_source": "api"},
    ]
    job = {
        "kind": "sample_bundle",
        "state": "succeeded",
        "update_existing": False,
        "submitted_by": "uploader",
        "staging_dir": "/synthetic/staged",
        "result": {"sample_id": "recover"},
    }
    jobs = [
        {**job, "update_existing": True, "submitted_by": "later-editor"},
        {**job, "state": "failed", "submitted_by": "failed-user"},
        job,
        {**job, "result": {"sample_id": "known"}},
    ]
    plan = plan_backfill(samples, jobs)
    assert len(plan) == 2
    assert plan[0]["set"] == {"ingested_by": "uploader", "ingest_source": "upload"}
    assert plan[1]["set"] == {"ingested_by": None, "ingest_source": None}
    assert plan[0]["selector"]["ingested_by"] == {"$exists": False}
    after = [
        {**sample, **next((p["set"] for p in plan if p["selector"]["_id"] == sample["_id"]), {})}
        for sample in samples
    ]
    assert plan_backfill(after, jobs) == []
