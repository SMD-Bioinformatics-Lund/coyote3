"""Retained audit protection, separated cleanup, and archival checkpoint regression tests."""

import json
from datetime import datetime, timedelta, timezone

import mongomock
import pytest
from bson import ObjectId

from api.infra.mongo.repositories import audit_integrity
from api.infra.mongo.repositories.app_controls import MongoAppControlsRepository
from api.infra.mongo.repositories.audit import AuditRepository
from api.infra.observability.audit_checkpoints import archive_checkpoint
from api.infra.security.mongo_roles import (
    identity_role,
    runtime_roles,
    verify_runtime_audit_permissions,
)
from scripts.database.manage_mongo_roles import POLICY, policy_text


def test_runtime_role_cannot_change_or_drop_clinical_audit_records():
    role = identity_role("synthetic_identity")
    protected = next(
        item for item in role["privileges"] if item["resource"]["collection"] == "audit_events"
    )
    assert set(protected["actions"]) == {"find", "insert", "listIndexes"}
    assert not role["roles"]
    assert all(item["resource"]["db"] == "synthetic_identity" for item in role["privileges"])
    assert POLICY.read_text() == policy_text()
    manifest = json.loads(POLICY.read_text())
    cursor = next(
        index for index in manifest["indexes"] if index["name"] == "idx_audit_notification_cursor"
    )
    assert cursor["fields"] == [["source.environment", 1], ["occurred_at", 1], ["_id", 1]]


def test_operational_replay_uses_insert_without_changing_existing_content():
    collection = mongomock.MongoClient().identity.operational_audit_events
    event = {"_id": ObjectId(), "message": "Original"}
    audit_integrity.append_event(collection, event)
    audit_integrity.append_event(collection, {**event, "message": "Replacement"})
    assert collection.count_documents({}) == 1
    assert collection.find_one()["message"] == "Original"


def test_identity_role_upgrade_does_not_grant_other_deployments_database_permissions():
    config = {
        "COYOTE3_MONGO_URI": "mongodb://primary/?replicaSet=app",
        "IDENTITY_MONGO_URI": "mongodb://identity/?replicaSet=identity",
        "KNOWLEDGEBASE_MONGO_URI": "mongodb://kb/?replicaSet=kb",
        "BAM_MONGO_URI": "mongodb://bam/?replicaSet=bam",
        "COYOTE3_DB": "clinical",
        "IDENTITY_DB": "clinical",
        "KNOWLEDGEBASE_DB": "references",
        "BAM_DB": "alignments",
    }
    assert runtime_roles(config) == [{"role": "coyote3_runtime_identity", "db": "clinical"}]


@pytest.mark.parametrize(
    "resource",
    [
        {"db": "identity", "collection": "audit_events"},
        {"db": "identity", "collection": ""},
        {"db": "", "collection": ""},
        {"anyResource": True},
    ],
)
def test_preflight_rejects_effective_destructive_audit_grants(resource):
    from types import SimpleNamespace

    client = SimpleNamespace(
        admin=SimpleNamespace(
            command=lambda *args, **kwargs: {
                "authInfo": {
                    "authenticatedUsers": [{"user": "synthetic"}],
                    "authenticatedUserPrivileges": [{"resource": resource, "actions": ["remove"]}],
                }
            }
        )
    )
    with pytest.raises(ValueError, match="alter retained audit history"):
        verify_runtime_audit_permissions(client, "identity")


def test_recent_events_include_both_collections_and_cleanup_never_touches_retained_history(
    monkeypatch,
):
    monkeypatch.setattr(
        audit_integrity, "run_transaction", lambda client, operation: operation(None)
    )
    monkeypatch.setattr(
        "api.infra.mongo.repositories.app_controls.run_transaction",
        lambda client, operation: operation(None),
    )
    client = mongomock.MongoClient(tz_aware=True)
    retained = client.identity.audit_events
    operational = client.identity.operational_audit_events
    repository = AuditRepository(retained, operational_collection=operational)
    old = datetime.now(timezone.utc) - timedelta(days=100)
    repository.persist(
        {
            "_id": ObjectId(),
            "retention_class": "traceability",
            "occurred_at": old,
            "source": {"environment": "test"},
            "message": "Retained",
        }
    )
    repository.persist(
        {
            "_id": ObjectId(),
            "retention_class": "operational",
            "occurred_at": old,
            "message": "Expiring",
        }
    )
    # Pre-upgrade operational events stay readable in their original collection.
    retained.insert_one(
        {
            "_id": ObjectId(),
            "retention_class": "operational",
            "occurred_at": old,
            "message": "Legacy operational",
        }
    )
    assert repository.recent_events(limit=10)["total"] == 3
    controls = MongoAppControlsRepository(client.app, identity_db=client.identity, config={})
    assert controls.delete_operational_audit_before(datetime.now(timezone.utc)) == 1
    assert retained.count_documents({}) == 2
    assert repository.recent_events(limit=10)["total"] == 2


def test_checkpoint_archive_preserves_previous_files_and_rejects_failed_verification(tmp_path):
    checkpoint = {"valid": True, "errors": [], "chains": [], "unchained_legacy_events": 0}
    first = archive_checkpoint(checkpoint, tmp_path)
    second = archive_checkpoint(checkpoint, tmp_path)
    assert first != second
    assert json.loads(first.read_text()) == checkpoint
    assert first.stat().st_mode & 0o777 == 0o440
    with pytest.raises(ValueError, match="Failed audit verification"):
        archive_checkpoint({**checkpoint, "valid": False}, tmp_path)
    assert len(list(tmp_path.iterdir())) == 2
    with pytest.raises(ValueError, match="existing dedicated directory"):
        archive_checkpoint(checkpoint, tmp_path / "not-mounted")
