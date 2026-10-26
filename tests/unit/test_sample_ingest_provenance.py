"""Initial sample attribution is server-owned and recovered only from creation evidence."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from api.infra.mongo.repositories.ingest_gateway import IngestCollectionGateway
from coyote3.application.ingest.collection_writes import (
    attribute_sample_import,
    upsert_collection_document,
)
from coyote3.application.ingest.jobs import sample_entry_source


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
        "created_by": "operator",
        "updated_by": "operator",
        "system_installed": False,
    }
    assert document["ingested_by"] == "forged"
    variant = attribute_sample_import("variants", document, "operator")
    assert variant["created_by"] == variant["updated_by"] == "operator"
    assert variant is not document


@pytest.mark.parametrize("existing", [None, {}, {"ingested_by": "first", "ingest_source": "api"}])
def test_sample_replacement_preserves_initial_attribution(monkeypatch, existing):
    collection = Mock()
    collection.find_one.return_value = existing
    collection.replace_one.return_value = SimpleNamespace(
        matched_count=1, modified_count=1, upserted_id=None
    )
    monkeypatch.setattr(
        "coyote3.application.ingest.collection_writes.normalize_collection_document",
        lambda name, document: document,
    )
    upsert_collection_document(
        SimpleNamespace(
            collection_gateway=IngestCollectionGateway(collections={"samples": collection})
        ),
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
