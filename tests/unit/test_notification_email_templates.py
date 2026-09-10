"""Verify MIME alternatives, sender selection, branding, and HTML escaping."""

from unittest.mock import MagicMock

import pytest

from api.infra.notifications.email import send_email
from api.infra.notifications.templates import render_email


@pytest.mark.parametrize("severity", ["info", "important", "warning", "critical", "success"])
def test_template_escapes_content_and_labels_severity(severity):
    html = render_email(
        subject='<script>alert("x")</script>',
        text_body="<img src=x>\nSecond line",
        severity=severity,
        environment="test",
        action_url="https://example.test/inbox",
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;img src=x&gt;<br>Second line" in html
    assert severity.upper() in html
    assert "TEST ENVIRONMENT" in html
    assert "cid:coyote3-logo" in html
    assert "do not reply" in html


def test_template_rejects_unsafe_actions():
    with pytest.raises(ValueError):
        render_email(
            subject="Test",
            text_body="Synthetic",
            severity="info",
            environment="test",
            action_url="javascript:alert(1)",
        )


def test_error_email_contains_downloadable_log_attachment(monkeypatch):
    smtp = MagicMock()
    monkeypatch.setattr("api.infra.notifications.email.smtplib.SMTP", smtp)
    assert send_email(
        config={
            "SMTP_HOST": "localhost",
            "SMTP_USE_TLS": False,
            "SMTP_FROM_EMAIL": "system@example.test",
        },
        to_email="monitor@example.test",
        subject="API error",
        text_body="Failure details",
        attachments=[("api_2026-09-09.log", b"synthetic diagnostic\n")],
    )
    message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
    attachment = next(message.iter_attachments())
    assert attachment.get_filename() == "api_2026-09-09.log"
    assert attachment.get_payload(decode=True) == b"synthetic diagnostic\n"


@pytest.mark.parametrize(
    ("purpose", "sender"),
    [
        ("account", "no-reply@example.test"),
        ("security", "security@example.test"),
        ("broadcast", "info@example.test"),
    ],
)
def test_email_contains_inline_logo_and_plain_text_alternative(monkeypatch, purpose, sender):
    smtp = MagicMock()
    monkeypatch.setattr("api.infra.notifications.email.smtplib.SMTP", smtp)
    assert send_email(
        config={
            "SMTP_HOST": "localhost",
            "SMTP_USE_TLS": False,
            "SMTP_FROM_EMAIL": "no-reply@example.test",
            "SMTP_SECURITY_FROM_EMAIL": "security@example.test",
            "SMTP_INFO_FROM_EMAIL": "info@example.test",
        },
        to_email="recipient@example.test",
        subject="Test",
        text_body="Synthetic",
        purpose=purpose,
        severity="important",
    )
    message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
    assert sender in message["From"]
    assert message["Reply-To"] == sender
    assert message["Auto-Submitted"] == "auto-generated"
    assert "Synthetic" in message.get_body(preferencelist=("plain",)).get_content()
    assert "IMPORTANT" in message.get_body(preferencelist=("html",)).get_content()
    image = next(part for part in message.walk() if part.get_content_type() == "image/png")
    assert image["Content-ID"] == "<coyote3-logo>"
    assert image.get_payload(decode=True).startswith(b"\x89PNG")
