"""Public error contracts and durable, redacted audit delivery."""

from unittest.mock import Mock

import pytest
from bson import ObjectId
from coyote.application.admin.app_controls import effective_audit_retention_days
from coyote.application.audit.service import AuditService
from coyote_mongo.audit_spool import AuditSpool
from coyote_mongo.repositories.app_controls import MongoAppControlsRepository
from coyote_mongo.repositories.audit import AuditRepository
from coyote_mongo.repositories.audit_outbox import audit_route
from pymongo.errors import AutoReconnect


def test_audit_outage_spools_sanitized_event_then_replays(tmp_path):
    collection = Mock()
    collection.insert_one.side_effect = AutoReconnect("synthetic outage")
    service = AuditService(
        AuditRepository(collection, operational_collection=collection, spool_directory=tmp_path),
        retention_days=90,
        environment="test",
    )
    identity = service.record("example.changed", "password=synthetic-secret", category="test")
    paths = list(tmp_path.glob("*.json"))
    assert len(paths) == 1
    assert paths[0].stem == identity
    assert "synthetic-secret" not in paths[0].read_text()
    assert paths[0].stat().st_mode & 0o777 == 0o600
    collection.insert_one.side_effect = None
    collection.insert_one.return_value.acknowledged = True
    assert service.replay_pending() == 1
    assert not list(tmp_path.glob("*.json"))
    assert collection.insert_one.call_args.args[0]["_id"] == ObjectId(identity)
    collection.update_one.assert_not_called()


def test_failed_replay_retains_original_identity_and_file(tmp_path):
    spool = AuditSpool(tmp_path)
    document = {"_id": ObjectId(), "message": "Synthetic event"}
    spool.persist(document)
    collection = Mock()
    collection.insert_one.side_effect = AutoReconnect("unknown acknowledgement")
    assert spool.replay(collection, operational_collection=collection) == 0
    assert len(list(tmp_path.glob("*.json"))) == 1
    collection.insert_one.side_effect = None
    collection.insert_one.return_value.acknowledged = True
    assert spool.replay(collection, operational_collection=collection) == 1
    assert collection.insert_one.call_args_list[0] == collection.insert_one.call_args_list[1]


def test_damaged_spool_file_does_not_block_valid_events(tmp_path, caplog):
    spool = AuditSpool(tmp_path)
    (tmp_path / "broken.json").write_text("not valid JSON")
    spool.persist({"_id": ObjectId(), "message": "Synthetic valid event"})
    destination = Mock()
    destination.insert_one.return_value.acknowledged = True
    assert spool.replay(destination, operational_collection=destination) == 1
    assert (tmp_path / "broken.invalid").read_text() == "not valid JSON"
    assert "retained for operator recovery" in caplog.text


def test_unacknowledged_writes_remain_pending(tmp_path):
    collection = Mock()
    collection.insert_one.return_value.acknowledged = False
    collection.update_one.return_value.acknowledged = False
    service = AuditService(
        AuditRepository(collection, operational_collection=collection, spool_directory=tmp_path),
        retention_days=90,
        environment="test",
    )
    identity = service.record("example.changed", "Synthetic event", category="test")
    assert (tmp_path / f"{identity}.json").exists()
    assert service.replay_pending() == 0
    assert (tmp_path / f"{identity}.json").exists()


def test_dual_storage_failure_is_not_silently_ignored(tmp_path, monkeypatch):
    collection = Mock()
    collection.insert_one.side_effect = AutoReconnect("synthetic outage")
    service = AuditService(
        AuditRepository(collection, operational_collection=collection, spool_directory=tmp_path),
        retention_days=90,
        environment="test",
    )
    monkeypatch.setattr(service.repository.spool, "persist", Mock(side_effect=OSError("disk full")))
    with pytest.raises(OSError, match="disk full"):
        service.record("example.changed", "Synthetic event", category="test")


def test_audit_retention_lookup_does_not_block_outage_spooling():
    collection = Mock()
    collection.find_one.side_effect = AutoReconnect("synthetic outage")
    from coyote_mongo.config.operational_collections import OPERATIONAL_COLLECTIONS

    assert (
        effective_audit_retention_days(
            MongoAppControlsRepository(
                {OPERATIONAL_COLLECTIONS.app_controls: collection},
                identity_db={"operational_audit_events": collection},
                config={},
            ),
            {"AUDIT_RETENTION_DAYS": 120},
        )
        == 120
    )


def test_outbox_route_ignores_credentials_but_separates_environments_and_databases():
    config = {
        "ENV_NAME": "development",
        "IDENTITY_DB": "identity_dev",
        "IDENTITY_MONGO_URI": "mongodb://user:old@mongo:27017/?replicaSet=app-rs",
    }
    route = audit_route(config)
    assert route == audit_route(
        {**config, "IDENTITY_MONGO_URI": "mongodb://user:new@mongo:27017/?replicaSet=app-rs"}
    )
    assert route != audit_route({**config, "ENV_NAME": "production"})
    assert route != audit_route({**config, "IDENTITY_DB": "another_identity"})
    assert route != audit_route(
        {**config, "IDENTITY_MONGO_URI": "mongodb://other:27017/?replicaSet=other-rs"}
    )
