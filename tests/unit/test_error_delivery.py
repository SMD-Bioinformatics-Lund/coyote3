"""Public error contracts and durable, redacted audit delivery."""

import json
import logging
from unittest.mock import Mock

import pytest
from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import AutoReconnect
from starlette.requests import Request

from api.application.admin.app_controls import effective_audit_retention_days
from api.application.audit.service import AuditService
from api.infra.mongo.repositories.audit_outbox import audit_route
from api.infra.observability.audit_spool import AuditSpool
from api.infra.observability.logging import JsonFormatter, request_context_from_request
from api.interfaces.http.errors import ERROR_GUIDANCE, error_response
from api.interfaces.http.operations.auth import http_exception_handler


def request(headers=()):
    """Build an isolated synthetic HTTP request."""
    return Request({"type": "http", "method": "GET", "path": "/synthetic", "headers": headers})


@pytest.mark.parametrize("status", ERROR_GUIDANCE)
def test_error_contract_has_actionable_hint_and_support_reference(status):
    req = request()
    response = error_response(req, status, "Example", details="password=synthetic-secret")
    body = json.loads(response.body)
    assert response.status_code == body["status"] == status
    assert body["code"] == ERROR_GUIDANCE[status][0]
    assert body["hint"]
    assert body["request_id"] == response.headers["x-request-id"]
    assert response.headers["cache-control"] == "no-store"
    if status == 401:
        assert response.headers["www-authenticate"] == "Bearer"
    assert "synthetic-secret" not in response.body.decode()
    if status >= 500:
        assert body["details"] is None
        assert body["error"] != "Example"


@pytest.mark.asyncio
async def test_http_exception_preserves_protocol_headers():
    result = await http_exception_handler(
        request(),
        HTTPException(
            405, detail="Unsupported method", headers={"Allow": "GET", "Retry-After": "10"}
        ),
    )
    assert result.headers["allow"] == "GET"
    assert result.headers["retry-after"] == "10"


def test_logging_redacts_credentials_in_messages_exceptions_and_nested_fields():
    record = logging.makeLogRecord(
        {
            "msg": "mongodb://synthetic-user:synthetic-password@mongo/db token=synthetic-token",
            "levelno": logging.ERROR,
            "levelname": "ERROR",
            "exc_text": "Authorization: Bearer synthetic-bearer",
            "diagnostics": {"password": "synthetic-password"},
            "failure": ValueError("password=synthetic-object-secret"),
        }
    )
    rendered = JsonFormatter().format(record)
    for secret in ("synthetic-user", "synthetic-password", "synthetic-token", "synthetic-bearer"):
        assert secret not in rendered
    assert "[redacted]" in rendered
    assert "synthetic-object-secret" not in rendered


@pytest.mark.parametrize("identity", ["x" * 129, "bad\nheader", "", "token=secret"])
def test_untrusted_request_ids_are_replaced(identity):
    context = request_context_from_request(request([(b"x-request-id", identity.encode())]))
    assert context.request_id != identity
    assert len(context.request_id) == 36


def test_audit_outage_spools_sanitized_event_then_replays(tmp_path):
    collection = Mock()
    collection.insert_one.side_effect = AutoReconnect("synthetic outage")
    service = AuditService(
        collection, retention_days=90, environment="test", spool_directory=tmp_path
    )
    identity = service.record("example.changed", "password=synthetic-secret", category="test")
    paths = list(tmp_path.glob("*.json"))
    assert len(paths) == 1
    assert paths[0].stem == identity
    assert "synthetic-secret" not in paths[0].read_text()
    assert paths[0].stat().st_mode & 0o777 == 0o600
    collection.update_one.return_value.acknowledged = True
    assert service.replay_pending() == 1
    assert not list(tmp_path.glob("*.json"))
    assert collection.update_one.call_args.args[0] == {"_id": ObjectId(identity)}
    assert "$setOnInsert" in collection.update_one.call_args.args[1]


def test_failed_replay_retains_original_identity_and_file(tmp_path):
    spool = AuditSpool(tmp_path)
    document = {"_id": ObjectId(), "message": "Synthetic event"}
    spool.persist(document)
    collection = Mock()
    collection.update_one.side_effect = AutoReconnect("unknown acknowledgement")
    assert spool.replay(collection) == 0
    assert len(list(tmp_path.glob("*.json"))) == 1
    collection.update_one.side_effect = None
    collection.update_one.return_value.acknowledged = True
    assert spool.replay(collection) == 1
    assert collection.update_one.call_args_list[0] == collection.update_one.call_args_list[1]


def test_damaged_spool_file_does_not_block_valid_events(tmp_path, caplog):
    spool = AuditSpool(tmp_path)
    (tmp_path / "broken.json").write_text("not valid JSON")
    spool.persist({"_id": ObjectId(), "message": "Synthetic valid event"})
    destination = Mock()
    destination.update_one.return_value.acknowledged = True
    assert spool.replay(destination) == 1
    assert (tmp_path / "broken.invalid").read_text() == "not valid JSON"
    assert "retained for operator recovery" in caplog.text


def test_unacknowledged_writes_remain_pending(tmp_path):
    collection = Mock()
    collection.insert_one.return_value.acknowledged = False
    collection.update_one.return_value.acknowledged = False
    service = AuditService(
        collection, retention_days=90, environment="test", spool_directory=tmp_path
    )
    identity = service.record("example.changed", "Synthetic event", category="test")
    assert (tmp_path / f"{identity}.json").exists()
    assert service.replay_pending() == 0
    assert (tmp_path / f"{identity}.json").exists()


def test_dual_storage_failure_is_not_silently_ignored(tmp_path, monkeypatch):
    collection = Mock()
    collection.insert_one.side_effect = AutoReconnect("synthetic outage")
    service = AuditService(
        collection, retention_days=90, environment="test", spool_directory=tmp_path
    )
    monkeypatch.setattr(service.spool, "persist", Mock(side_effect=OSError("disk full")))
    with pytest.raises(OSError, match="disk full"):
        service.record("example.changed", "Synthetic event", category="test")


def test_audit_retention_lookup_does_not_block_outage_spooling():
    collection = Mock()
    collection.find_one.side_effect = AutoReconnect("synthetic outage")
    from api.config.contracts.application import OPERATIONAL_COLLECTIONS

    assert (
        effective_audit_retention_days(
            {OPERATIONAL_COLLECTIONS.app_controls: collection}, {"AUDIT_RETENTION_DAYS": 120}
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


@pytest.mark.asyncio
async def test_unhandled_error_preserves_actor_and_context_and_survives_audit_failure(monkeypatch):
    from api.app.main import unhandled_exception_handler
    from api.infra.observability.logging import current_request_context

    req = request()
    req.state.request_id = "failure-reference"
    req.state.authenticated_user = "synthetic-user"
    recorder = Mock()

    def record(*args, **kwargs):
        assert kwargs["actor"] == "synthetic-user"
        assert current_request_context().request_id == "failure-reference"
        raise OSError("synthetic disk failure")

    recorder.record.side_effect = record
    monkeypatch.setattr("api.app.deps.services.get_audit_service", lambda: recorder)
    response = await unhandled_exception_handler(req, RuntimeError("private diagnostic"))
    assert response.status_code == 500
    assert response.headers["x-request-id"] == "failure-reference"
    assert b"private diagnostic" not in response.body
    recorder.record.assert_called_once()
