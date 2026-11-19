"""Knowledgebase and identity relocation on a disposable MongoDB replica."""

import pytest

from scripts.identity.migrate_identity_database import STAGING_PREFIX
from scripts.knowledgebase.migrate_knowledgebase_database import migrate_collection
from tests.fixtures.mongo_settings import audit_context
from tests.integration.test_ingest_job_recovery import database as _database

database = _database


@pytest.fixture
def migration_databases(database):
    source, _, _ = database
    target = source.client[source.name + "_dst"]
    try:
        yield source, target
    finally:
        source.client.drop_database(target.name)


def test_migration_copies_indexes_and_verifies_transformed_content(
    migration_databases,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, target = migration_databases
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
        "scripts.knowledgebase.migrate_knowledgebase_database.source_collection_options",
        lambda *_args: {},
    )

    result = migrate_collection(
        source,
        target,
        "oncokb_public_collection",
        "oncokb_public",
        apply=True,
        context=audit_context(),
    )

    assert result["status"] == "migrated"
    assert result["verified"] is True
    assert target.oncokb_public.count_documents({}) == 1
    migrated = target.oncokb_public.find_one({"_id": "one"})
    assert "sample_ids" not in migrated
    assert "sample_names" not in migrated
    assert "query_hash_1" in target.oncokb_public.index_information()


def test_identity_migration_preserves_documents_and_indexes(
    migration_databases, monkeypatch
) -> None:
    source, target = migration_databases
    source.users.insert_one({"_id": "one", "username": "local-user"})
    source.users.create_index("username", name="username_1", unique=True)
    monkeypatch.setattr(
        "scripts.knowledgebase.migrate_knowledgebase_database.source_collection_options",
        lambda *_args: {},
    )

    result = migrate_collection(
        source,
        target,
        "users_collection",
        "users",
        apply=True,
        staging_prefix=STAGING_PREFIX,
        context=audit_context(),
    )

    assert result["status"] == "migrated"
    assert result["verified"] is True
    assert target.users.find_one({"_id": "one"})["username"] == "local-user"
    assert "username_1" in target.users.index_information()
