"""Reference relocation and legacy registry retirement safety checks."""

import mongomock
import pytest

from scripts.migrate_reference_database import migrate, validate_legacy_subpanels


def test_missing_replacement_blocks_retirement():
    db = mongomock.MongoClient().app
    db.assay_subpanels.insert_one({"asp_id": "demo", "subpanel_id": "named", "is_current": True})
    with pytest.raises(ValueError, match="no current replacement"):
        validate_legacy_subpanels(db)
    db.subpanels.insert_one({"subpanel_id": "named", "is_current": True})
    db.subpanel_associations.insert_one(
        {"asp_id": "demo", "subpanel_id": "named", "is_current": True, "is_active": False}
    )
    assert validate_legacy_subpanels(db) == 1


def test_dry_run_does_not_copy_or_delete():
    client = mongomock.MongoClient()
    client.app.hgnc_genes.insert_one({"_id": "gene", "symbol": "SYNTHETIC"})
    client.app.vep_metadata.insert_one({"_id": "version", "vep_id": "113"})
    result = migrate(client.app, client.kb)
    assert [row["status"] for row in result["references"]] == ["ready", "ready"]
    assert client.kb.list_collection_names() == []
    assert client.app.hgnc_genes.count_documents({}) == 1


def test_conflicting_destination_retains_source(tmp_path):
    client = mongomock.MongoClient()
    client.app.vep_metadata.insert_one({"_id": "release", "vep_id": "113"})
    client.kb.vep_metadata.insert_one({"_id": "release", "vep_id": "110"})
    with pytest.raises(RuntimeError, match="differs"):
        migrate(client.app, client.kb, apply=True, backup_dir=tmp_path / "backup")
    assert client.app.vep_metadata.find_one()["vep_id"] == "113"
    assert not (tmp_path / "backup").exists()


def test_apply_requires_backup_directory():
    client = mongomock.MongoClient()
    with pytest.raises(ValueError, match="backup-dir"):
        migrate(client.app, client.kb, apply=True)


def test_apply_backs_up_and_verifies_before_removing_sources(tmp_path, monkeypatch):
    from bson import decode_all

    client = mongomock.MongoClient()
    client.app.hgnc_genes.insert_one({"_id": "gene", "symbol": "SYNTHETIC"})
    client.app.vep_metadata.insert_one({"_id": "version", "vep_id": "113"})
    client.app.assay_subpanels.insert_one(
        {"_id": "base", "subpanel_id": "base", "is_current": True}
    )
    monkeypatch.setattr(
        "scripts.migrate_knowledgebase_database.source_collection_options", lambda *_: {}
    )
    monkeypatch.setattr(mongomock.collection.Collection, "options", lambda self: {}, raising=False)
    backup = tmp_path / "backup"
    result = migrate(client.app, client.kb, apply=True, backup_dir=backup)
    assert result["sources_removed"]
    assert client.app.list_collection_names() == []
    assert client.kb.hgnc_genes.find_one()["symbol"] == "SYNTHETIC"
    assert client.kb.vep_metadata.find_one()["vep_id"] == "113"
    assert decode_all((backup / "assay_subpanels.bson").read_bytes())[0]["_id"] == "base"
    assert (backup / "hgnc_genes.bson").stat().st_mode & 0o777 == 0o600
    assert migrate(client.app, client.kb)["legacy_documents"] == 0
