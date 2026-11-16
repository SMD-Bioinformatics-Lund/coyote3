"""Initial sample attribution is server-owned and recovered only from creation evidence."""

import pytest
from coyote.application.ingest.collection_writes import attribute_sample_import
from coyote.application.ingest.jobs import sample_entry_source


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
