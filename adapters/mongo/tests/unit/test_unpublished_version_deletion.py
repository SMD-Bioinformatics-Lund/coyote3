"""Verify unpublished workspace deletion without accessing installed databases."""

from types import SimpleNamespace
from unittest.mock import Mock

import mongomock
import pytest
from bson import ObjectId
from coyote_mongo.repositories import public_assay_catalog_versions
from mongo_test_support.settings import mongo_runtime


@pytest.mark.parametrize(
    "status", ["draft", "submitted", "approved", "rejected", "published", "retired"]
)
@pytest.mark.parametrize("revision", [1, 2])
def test_deletion_checks_state_and_revision_and_preserves_other_records(
    monkeypatch, status, revision
):
    """Remove only eligible versions and their snapshots, retaining an audit receipt."""
    db = mongomock.MongoClient().synthetic
    oid, other = ObjectId(), ObjectId()
    db.versions.insert_many(
        [
            {"_id": oid, "revision": 1, "status": status, "asp_id": "demo"},
            {"_id": other, "revision": 1, "status": "published"},
        ]
    )
    key = "version_id"
    db.snapshots.insert_many([{key: str(oid)}, {key: str(other)}])
    db.live.insert_one({"name": "existing publication"})
    module = public_assay_catalog_versions
    repository = module.PublicAssayCatalogVersionRepository(
        SimpleNamespace(
            app=mongo_runtime(),
            public_assay_catalog_versions_collection=db.versions,
            public_assay_catalog_revisions_collection=db.snapshots,
        )
    )
    allowed = {"draft", "submitted", "approved", "rejected"}
    audit = Mock()
    monkeypatch.setattr(module, "run_transaction", lambda client, operation: operation(None))
    monkeypatch.setattr(module, "enqueue_audit", audit)
    result = repository.delete_unpublished(str(oid), revision, "operator")
    deleted = status in allowed and revision == 1
    assert (result is not None) == deleted
    assert (db.versions.find_one({"_id": oid}) is None) == deleted
    assert db.snapshots.count_documents({key: str(oid)}) == (0 if deleted else 1)
    assert db.versions.find_one({"_id": other})["status"] == "published"
    assert db.snapshots.count_documents({key: str(other)}) == 1
    assert db.live.count_documents({}) == 1
    assert audit.call_count == int(deleted)
    if deleted:
        assert audit.call_args.kwargs["actor"] == "operator"
        assert audit.call_args.kwargs["metadata"]["status"] == status
