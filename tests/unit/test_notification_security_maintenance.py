"""Focused tests for notification transport, security indexes, and maintenance tasks."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import mongomock
from pymongo.errors import OperationFailure

from api.infra.notifications import email
from api.infra.security.indexes import _create_index, ensure_security_indexes
from api.tasks import maintenance


class _SmtpServer:
    def __init__(self, *_args, **_kwargs) -> None:
        self.started_tls = False
        self.credentials: tuple[str, str] | None = None
        self.message = None

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.credentials = (username, password)

    def send_message(self, message) -> None:
        self.message = message


def test_smtp_configuration_and_unconfigured_send(monkeypatch) -> None:
    """Incomplete SMTP configuration skips transport and emits an operational metric."""
    metrics: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        email, "emit_mail_metric", lambda event, **labels: metrics.append((event, labels))
    )
    assert email.smtp_configured({}) is False
    assert email.smtp_configured({"SMTP_HOST": "smtp.test", "SMTP_FROM_EMAIL": " "}) is False
    assert email.smtp_configured(
        {"SMTP_HOST": "smtp.test", "SMTP_FROM_EMAIL": "coyote@example.test"}
    )
    assert (
        email.send_email(config={}, to_email="user@example.test", subject="Test", text_body="Body")
        is False
    )
    assert metrics == [("send_skipped", {"reason": "smtp_not_configured"})]


def test_plain_starttls_and_ssl_email_paths(monkeypatch) -> None:
    """SMTP transport honors TLS, authentication, SSL, and message metadata."""
    servers: list[_SmtpServer] = []
    metrics: list[tuple[str, dict]] = []

    def factory(*args, **kwargs):
        server = _SmtpServer(*args, **kwargs)
        servers.append(server)
        return server

    monkeypatch.setattr(email.smtplib, "SMTP", factory)
    monkeypatch.setattr(email.smtplib, "SMTP_SSL", factory)
    monkeypatch.setattr(
        email, "emit_mail_metric", lambda event, **labels: metrics.append((event, labels))
    )
    base = {
        "SMTP_HOST": "smtp.test",
        "SMTP_PORT": 2525,
        "SMTP_FROM_EMAIL": "coyote@example.test",
        "SMTP_FROM_NAME": "Clinical Coyote",
        "SMTP_USERNAME": "service",
        "SMTP_PASSWORD": "secret",
    }
    assert email.send_email(
        config=base,
        to_email=" user@example.test ",
        subject="Review ready",
        text_body="A report is ready.",
    )
    assert servers[0].started_tls is True
    assert servers[0].credentials == ("service", "secret")
    assert servers[0].message["From"] == "Clinical Coyote <coyote@example.test>"
    assert servers[0].message["To"] == "user@example.test"

    assert email.send_email(
        config={**base, "SMTP_USE_SSL": True, "SMTP_USE_TLS": False, "SMTP_USERNAME": ""},
        to_email="user@example.test",
        subject="SSL",
        text_body="Body",
    )
    assert servers[1].started_tls is False
    assert servers[1].credentials is None
    assert any(
        event == "send_result" and labels.get("outcome") == "success" for event, labels in metrics
    )


def test_email_transport_failure_is_reported(monkeypatch) -> None:
    """Transport failures return false without exposing the exception to callers."""
    metrics: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        email, "emit_mail_metric", lambda event, **labels: metrics.append((event, labels))
    )

    def fail(*_args, **_kwargs):
        raise OSError("SMTP unavailable")

    monkeypatch.setattr(email.smtplib, "SMTP", fail)
    assert (
        email.send_email(
            config={"SMTP_HOST": "smtp.test", "SMTP_FROM_EMAIL": "coyote@example.test"},
            to_email="user@example.test",
            subject="Failure",
            text_body="Body",
            log=logging.getLogger("test.smtp"),
        )
        is False
    )
    assert metrics[-1][1]["outcome"] == "failed"
    assert metrics[-1][1]["error"] == "OSError"


def test_security_indexes_are_created_and_failures_are_nonfatal() -> None:
    """Security collections receive required indexes while one conflict is logged."""
    database = mongomock.MongoClient()["coyote3_test"]
    logger = logging.getLogger("test.security.indexes")
    ensure_security_indexes(db=database, config={}, logger=logger)
    assert "ttl_api_session_expiry" in database.api_sessions.index_information()
    assert (
        database.api_sessions.index_information()["ttl_api_session_expiry"]["expireAfterSeconds"]
        == 0
    )
    assert "idx_audit_actor_time" in database.audit_events.index_information()
    assert database.app_controls.index_information()["uniq_app_controls_control_id"]["unique"]

    class BrokenCollection:
        name = "broken"

        def create_index(self, *_args, **_kwargs):
            raise OperationFailure("conflict")

    _create_index(BrokenCollection(), [("field", 1)], name="broken_index", logger=logger)


def test_retention_task_disabled_and_enabled(monkeypatch) -> None:
    """The task gate prevents work and enabled execution serializes the service result."""
    monkeypatch.setattr(maintenance, "_ensure_worker_runtime", lambda: None)
    monkeypatch.setattr(maintenance, "task_family_enabled", lambda _family: False)
    monkeypatch.setattr(maintenance, "disabled_result", lambda family: {"disabled": family})
    assert maintenance.run_retention_maintenance.run() == {"disabled": "maintenance"}

    service = SimpleNamespace(run_maintenance=lambda: {"removed": 4})
    monkeypatch.setattr(maintenance, "task_family_enabled", lambda _family: True)
    monkeypatch.setattr(maintenance, "get_app_controls_service", lambda: service)
    monkeypatch.setattr(maintenance, "_serializable", lambda value: {**value, "serialized": True})
    assert maintenance.run_retention_maintenance.run() == {"removed": 4, "serialized": True}


def test_public_oncokb_refresh_task_obeys_maintenance_gate(monkeypatch) -> None:
    """The global public-reference refresh uses the maintenance task family."""
    monkeypatch.setattr(maintenance, "_ensure_worker_runtime", lambda: None)
    monkeypatch.setattr(maintenance, "task_family_enabled", lambda _family: False)
    monkeypatch.setattr(maintenance, "disabled_result", lambda family: {"disabled": family})
    assert maintenance.refresh_public_oncokb.run() == {"disabled": "maintenance"}

    service = SimpleNamespace(refresh=lambda: {"status": "ok", "curated_genes_upserted": 8})
    monkeypatch.setattr(maintenance, "task_family_enabled", lambda _family: True)
    monkeypatch.setattr(maintenance, "get_public_oncokb_refresh_service", lambda: service)
    monkeypatch.setattr(maintenance, "_serializable", lambda value: {**value, "serialized": True})
    assert maintenance.refresh_public_oncokb.run() == {
        "status": "ok",
        "curated_genes_upserted": 8,
        "serialized": True,
    }


def test_dashboard_refresh_task_deduplicates_equivalent_user_scopes(monkeypatch, tmp_path) -> None:
    """Periodic refresh computes each distinct active access scope once."""
    monkeypatch.setattr(maintenance, "_ensure_worker_runtime", lambda: None)
    monkeypatch.setattr(maintenance, "task_family_enabled", lambda _family: True)
    monkeypatch.setattr(
        maintenance,
        "DASHBOARD_REFRESH_LOCK_PATH",
        str(tmp_path / "dashboard-refresh.lock"),
    )
    users = [
        {"username": "one", "is_active": True},
        {"username": "two", "is_active": True},
        {"username": "inactive", "is_active": False},
    ]
    refreshed: list[str] = []
    shared_payload = {"global": "metrics"}
    service = SimpleNamespace(
        user_repository=SimpleNamespace(get_all_users=lambda: users),
        build_shared_summary_payload=lambda: shared_payload,
        summary_scope_key=lambda *, user: "shared" if user.username in {"one", "two"} else "other",
        refresh_summary_payload=lambda *, user, shared_payload: refreshed.append(user.username)
        or {"shared_payload": shared_payload},
    )
    monkeypatch.setattr(maintenance, "get_dashboard_service", lambda: service)
    monkeypatch.setattr(
        maintenance,
        "api_user_from_user_doc",
        lambda doc: SimpleNamespace(username=doc["username"]),
    )
    monkeypatch.setattr(maintenance, "_serializable", lambda value: value)

    result = maintenance.refresh_dashboard_metrics.run()

    assert result == {
        "status": "completed",
        "refreshed": 1,
        "skipped": 2,
        "failures": [],
    }
    assert refreshed == ["one"]
