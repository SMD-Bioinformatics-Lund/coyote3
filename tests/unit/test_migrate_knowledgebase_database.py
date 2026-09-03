"""Tests for the dedicated knowledgebase database migration."""

from __future__ import annotations

from pathlib import Path

import mongomock
import pytest

from scripts.migrate_knowledgebase_database import (
    knowledgebase_collections,
    migrate_collection,
    transformed_documents,
)


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


def test_migration_copies_indexes_and_verifies_transformed_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = mongomock.MongoClient()
    source = client.application
    target = client.knowledgebase
    source.oncokb_public.insert_one(
        {
            "_id": "one",
            "query_hash": "hash",
            "gene": "TP53",
            "sample_ids": ["sample-oid"],
            "sample_names": ["synthetic-sample"],
        }
    )
    source.oncokb_public.create_index("query_hash", name="query_hash_1", unique=True)
    monkeypatch.setattr(
        "scripts.migrate_knowledgebase_database.source_collection_options",
        lambda *_args: {},
    )

    result = migrate_collection(
        source,
        target,
        "oncokb_public_collection",
        "oncokb_public",
        apply=True,
    )

    assert result["status"] == "migrated"
    assert result["verified"] is True
    assert target.oncokb_public.count_documents({}) == 1
    migrated = target.oncokb_public.find_one({"_id": "one"})
    assert "sample_ids" not in migrated
    assert "sample_names" not in migrated
    assert "query_hash_1" in target.oncokb_public.index_information()


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
        )

    assert client.knowledgebase.civic.find_one({"_id": "one"})["gene"] == "KRAS"
