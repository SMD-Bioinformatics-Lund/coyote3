"""Copied ASPCs remain resolvable by runtime scope with a user-chosen ID."""

from types import SimpleNamespace

import mongomock
import pytest
from coyote.domain.exceptions import AppError
from coyote_mongo.repositories.assay_configurations import ASPConfigRepository
from mongo_test_support.settings import mongo_runtime


def test_custom_identity_resolves_by_scope_and_duplicate_scope_is_rejected(monkeypatch):
    monkeypatch.setattr(
        "coyote_mongo.repositories.assay_components.run_transaction",
        lambda _client, callback: callback(None),
    )
    monkeypatch.setattr(
        "coyote_mongo.repositories.assay_components.enqueue_audit", lambda *_a, **_k: None
    )
    db = mongomock.MongoClient().db
    adapter = SimpleNamespace(
        app=mongo_runtime(),
        aspc_collection=db.configs,
        asp_collection=db.panels,
        assay_groups_collection=db.groups,
        insilico_genelist_collection=db.lists,
    )
    db.groups.insert_one({"group_id": "demo", "is_active": True})
    db.panels.insert_one(
        {"asp_id": "synthetic", "asp_group": "demo", "asp_category": "dna", "is_active": True}
    )
    repository = ASPConfigRepository(adapter)
    monkeypatch.setattr(repository, "invalidate_dashboard_metrics", lambda: None)
    repository.ensure_indexes()
    document = {
        "aspc_id": "chosen-copy-id",
        "asp_id": "synthetic",
        "diagnosis_id": "base",
        "asp_group": "demo",
        "asp_category": "dna",
        "environment": "production",
        "is_active": True,
        "version": 1,
        "created_by": "test",
    }
    repository.create_assay_config(document)
    assert repository.get_aspc("SYNTHETIC", "production")["aspc_id"] == "chosen-copy-id"
    assert repository.get_aspc_no_meta("synthetic")["aspc_id"] == "chosen-copy-id"
    assert "created_by" not in repository.get_aspc_no_meta("synthetic")
    with pytest.raises(AppError, match="configuration scope"):
        repository.create_assay_config({**document, "aspc_id": "another-id"})
