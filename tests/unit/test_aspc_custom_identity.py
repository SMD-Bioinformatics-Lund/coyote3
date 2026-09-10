"""Copied ASPCs remain resolvable by runtime scope with a user-chosen ID."""

from types import SimpleNamespace

import mongomock
import pytest

from api.domain.core.exceptions import AppError
from api.infra.mongo.repositories.assay_configurations import ASPConfigRepository


def test_custom_identity_resolves_by_scope_and_duplicate_scope_is_rejected(monkeypatch):
    repository = ASPConfigRepository(
        SimpleNamespace(aspc_collection=mongomock.MongoClient().db.configs)
    )
    monkeypatch.setattr(repository, "invalidate_dashboard_metrics", lambda: None)
    repository.ensure_indexes()
    document = {
        "aspc_id": "chosen-copy-id",
        "asp_id": "synthetic",
        "subpanel_id": "base",
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
