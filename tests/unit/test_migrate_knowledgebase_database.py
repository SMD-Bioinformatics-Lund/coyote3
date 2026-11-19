"""Tests for the dedicated knowledgebase database migration."""

from __future__ import annotations

from pathlib import Path

import mongomock
import pytest

from scripts.knowledgebase.migrate_knowledgebase_database import (
    knowledgebase_collections,
    migrate_collection,
    transformed_documents,
)
from tests.fixtures.mongo_settings import audit_context


def test_knowledgebase_collection_mapping_is_explicit(tmp_path: Path) -> None:
    config = tmp_path / "collections.toml"
    config.write_text(
        '[primary]\nsamples_collection = "samples"\n'
        '[knowledgebase]\ncivic_collection = "civic"\n'
        '[bam]\nbam_samples = "samples"\n',
        encoding="utf-8",
    )

    assert knowledgebase_collections(config) == {"civic_collection": "civic"}


def test_only_oncokb_public_drops_forbidden_sample_fields() -> None:
    document = {
        "_id": "one",
        "query_hash": "hash",
        "sample_ids": ["sample-oid"],
        "sample_names": ["synthetic-sample"],
    }

    transformed = list(transformed_documents("oncokb_public_collection", [document]))[0]
    unchanged = list(transformed_documents("other_collection", [document]))[0]

    assert "sample_ids" not in transformed
    assert "sample_names" not in transformed
    assert unchanged == document
    assert document["sample_ids"] == ["sample-oid"]


def test_existing_different_target_is_never_overwritten() -> None:
    client = mongomock.MongoClient()
    client.application.civic.insert_one({"_id": "one", "gene": "TP53"})
    client.knowledgebase.civic.insert_one({"_id": "one", "gene": "KRAS"})

    with pytest.raises(RuntimeError, match="Target differs from source"):
        migrate_collection(
            client.application,
            client.knowledgebase,
            "civic_variants_collection",
            "civic",
            apply=True,
            context=audit_context(),
        )

    assert client.knowledgebase.civic.find_one({"_id": "one"})["gene"] == "KRAS"
