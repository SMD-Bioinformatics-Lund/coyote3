"""Copied ASPCs remain resolvable by runtime scope with a user-chosen ID."""

from types import SimpleNamespace

import mongomock
import pytest
from coyote.domain.exceptions import AppError
from coyote_mongo.repositories.assay_configurations import ASPConfigRepository
from mongo_test_support.settings import mongo_runtime


def test_custom_identity_resolves_by_scope_and_duplicate_scope_is_rejected(monkeypatch):
    monkeypatch.setattr(
        "coyote_mongo.repositories.audit_outbox.run_transaction",
        lambda _client, callback: callback(None),
    )
    monkeypatch.setattr(
        "coyote_mongo.repositories.audit_outbox.enqueue_audit", lambda *_a, **_k: None
    )
    repository = ASPConfigRepository(
        SimpleNamespace(app=mongo_runtime(), aspc_collection=mongomock.MongoClient().db.configs)
    )
    monkeypatch.setattr(repository, "invalidate_dashboard_metrics", lambda: None)
    repository.ensure_indexes()
    document = {
        "aspc_id": "chosen-copy-id",
        "asp_id": "synthetic",
        "diagnosis_id": "base",
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
