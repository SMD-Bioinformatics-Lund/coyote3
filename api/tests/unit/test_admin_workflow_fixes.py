"""Regression checks for managed forms, ingestion diagnostics, and email control wiring."""

from types import SimpleNamespace
from unittest.mock import Mock


def test_email_config_reads_current_control(monkeypatch):
    from coyote_api.app.deps import services

    controls = SimpleNamespace(email=SimpleNamespace(enabled=False))
    service = Mock()
    service.get_controls.return_value = controls
    monkeypatch.setattr(services, "get_app_controls_service", lambda: service)
    assert services.get_email_config()["EMAIL_ENABLED"] is False
    controls.email.enabled = True
    assert services.get_email_config()["EMAIL_ENABLED"] is True
