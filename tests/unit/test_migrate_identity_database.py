"""Tests for the dedicated identity database migration."""

from __future__ import annotations

from pathlib import Path

import mongomock

from scripts.migrate_identity_database import STAGING_PREFIX, identity_collections
from scripts.migrate_knowledgebase_database import migrate_collection


def test_identity_collection_mapping_is_explicit(tmp_path: Path) -> None:
    config = tmp_path / "collections.toml"
    config.write_text(
        '[primary]\nsamples_collection = "samples"\n'
        '[identity]\nusers_collection = "users"\naudit_events_collection = "audit_events"\n'
        '[knowledgebase]\ncivic_collection = "civic"\n'
        '[bam]\nbam_samples = "samples"\n',
        encoding="utf-8",
    )

    assert identity_collections(config) == {
        "users_collection": "users",
        "audit_events_collection": "audit_events",
    }


def test_identity_migration_preserves_documents_and_indexes(monkeypatch) -> None:
    client = mongomock.MongoClient()
    source = client.application
    target = client.identity
    source.users.insert_one({"_id": "one", "username": "local-user"})
    source.users.create_index("username", name="username_1", unique=True)
    monkeypatch.setattr(
        "scripts.migrate_knowledgebase_database.source_collection_options",
        lambda *_args: {},
    )

    result = migrate_collection(
        source,
        target,
        "users_collection",
        "users",
        apply=True,
        staging_prefix=STAGING_PREFIX,
    )

    assert result["status"] == "migrated"
    assert result["verified"] is True
    assert target.users.find_one({"_id": "one"})["username"] == "local-user"
    assert "username_1" in target.users.index_information()
