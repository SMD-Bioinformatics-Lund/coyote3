"""Focused tests for notification transport, security indexes, and maintenance tasks."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import mongomock
from api_test_support.mongo_settings import mongo_runtime
from coyote_api.app.deps import services
from coyote_api.infra.notifications import email
from coyote_api.security import access
from coyote_api.tasks import maintenance
from coyote_mongo.index_management import _ContractCollection
from coyote_mongo.repositories.notifications import NotificationsRepository


def test_disabled_email_never_opens_smtp(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("SMTP must not be contacted while email is disabled")

    monkeypatch.setattr(email.smtplib, "SMTP", forbidden)
    monkeypatch.setattr(email.smtplib, "SMTP_SSL", forbidden)
    config = {
        "SMTP_HOST": "smtp.test",
        "SMTP_FROM_EMAIL": "sender@example.test",
        "EMAIL_ENABLED": False,
    }
    assert not email.smtp_configured(config)
    assert not email.send_email(
        config=config, to_email="user@example.test", subject="Test", text_body="Test"
    )


class _SmtpServer:
    def __init__(self, *_args, **_kwargs) -> None:
        self.started_tls = False
        self.credentials: tuple[str, str] | None = None
        self.message = None

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def starttls(self, *, context) -> None:
        assert context.check_hostname
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.credentials = (username, password)

    def send_message(self, message) -> None:
        self.message = message


def test_notification_indexes_support_read_only_startup_contract_inspection():
    collection = mongomock.MongoClient().test.notifications
    recorder = _ContractCollection(collection, "notifications")
    repo = NotificationsRepository(
        SimpleNamespace(app=mongo_runtime(), notifications_collection=recorder)
    )
    repo.ensure_indexes()
    assert len(recorder.contracts) == 4


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


def test_retention_task_disabled_and_enabled(monkeypatch) -> None:
    """The task gate prevents work and enabled execution serializes the service result."""
    monkeypatch.setattr(maintenance, "ensure_worker_runtime", lambda: None)
    monkeypatch.setattr(maintenance, "task_family_enabled", lambda _family: False)
    monkeypatch.setattr(maintenance, "disabled_result", lambda family: {"disabled": family})
    assert maintenance.run_retention_maintenance.run() == {"disabled": "maintenance"}

    service = SimpleNamespace(run_maintenance=lambda: {"removed": 4})
    monkeypatch.setattr(maintenance, "task_family_enabled", lambda _family: True)
    monkeypatch.setattr(services, "get_app_controls_service", lambda: service)
    monkeypatch.setattr(maintenance, "serializable", lambda value: {**value, "serialized": True})
    assert maintenance.run_retention_maintenance.run() == {"removed": 4, "serialized": True}


def test_public_oncokb_refresh_task_obeys_maintenance_gate(monkeypatch) -> None:
    """The global public-reference refresh uses the maintenance task family."""
    monkeypatch.setattr(maintenance, "ensure_worker_runtime", lambda: None)
    monkeypatch.setattr(maintenance, "task_family_enabled", lambda _family: False)
    monkeypatch.setattr(maintenance, "disabled_result", lambda family: {"disabled": family})
    assert maintenance.refresh_public_oncokb.run() == {"disabled": "maintenance"}

    service = SimpleNamespace(refresh=lambda: {"status": "ok", "curated_genes_upserted": 8})
    monkeypatch.setattr(maintenance, "task_family_enabled", lambda _family: True)
    monkeypatch.setattr(services, "get_public_oncokb_refresh_service", lambda: service)
    monkeypatch.setattr(maintenance, "serializable", lambda value: {**value, "serialized": True})
    assert maintenance.refresh_public_oncokb.run() == {
        "status": "ok",
        "curated_genes_upserted": 8,
        "serialized": True,
    }


def test_dashboard_refresh_task_deduplicates_equivalent_user_scopes(monkeypatch, tmp_path) -> None:
    """Periodic refresh computes each distinct active access scope once."""
    monkeypatch.setattr(maintenance, "ensure_worker_runtime", lambda: None)
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
    refreshed: list[tuple[str, str]] = []
    released: list[tuple[str, str]] = []
    service = SimpleNamespace(
        user_repository=SimpleNamespace(get_all_users=lambda: users),
        metric_scope_key=lambda metric, *, user: f"{metric}:shared",
        metric_payload=lambda metric, *, user, force: (
            refreshed.append((user.username, metric)) or {"metric": metric}
        ),
        release_metric_refresh=lambda metric, *, user: released.append((user.username, metric)),
    )
    monkeypatch.setattr(services, "get_dashboard_service", lambda: service)
    monkeypatch.setattr(
        access,
        "api_user_from_user_doc",
        lambda doc: SimpleNamespace(username=doc["username"]),
    )
    monkeypatch.setattr(maintenance, "serializable", lambda value: value)

    result = maintenance.refresh_dashboard_metrics.run(metrics=["samples", "findings"])

    assert result == {
        "status": "completed",
        "refreshed": 2,
        "skipped": 3,
        "failures": [],
    }
    assert refreshed == [("one", "findings"), ("one", "samples")]
    assert released == [
        ("one", "findings"),
        ("one", "samples"),
    ]
