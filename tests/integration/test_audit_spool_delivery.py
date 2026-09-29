"""Verify idempotent audit replay against a disposable MongoDB collection."""

import os
from uuid import uuid4

import pytest
from bson import ObjectId
from pymongo import MongoClient

from api.infra.observability.audit_spool import AuditSpool


def test_replaying_an_already_committed_event_keeps_one_immutable_record(tmp_path):
    uri = os.getenv("AUDIT_TEST_MONGO_URI")
    if not uri:
        pytest.skip("Set AUDIT_TEST_MONGO_URI for disposable audit recovery tests")
    with MongoClient(uri, serverSelectionTimeoutMS=3000) as client:
        db = client[f"coyote3_audit_test_{uuid4().hex}"]
        try:
            original = {"_id": ObjectId(), "message": "Original synthetic event"}
            db.audit_events.insert_one(original)
            spool = AuditSpool(tmp_path)
            spool.persist({**original, "message": "Must not replace the original"})
            assert spool.replay(db.audit_events) == 1
            assert db.audit_events.count_documents({}) == 1
            assert db.audit_events.find_one({"_id": original["_id"]}) == original
            assert not list(tmp_path.glob("*.json"))
        finally:
            client.drop_database(db.name)
