"""SMTP delivery of branded multipart account and broadcast notifications."""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from functools import lru_cache
from pathlib import Path
from typing import Any

from api.config.paths import EMAIL_LOGO_PATH
from api.infra.notifications.templates import render_email
from api.infra.observability.auth_metrics import emit_mail_metric

logger = logging.getLogger("api.infra.notifications.email")


@lru_cache(maxsize=1)
def _logo_bytes() -> bytes:
    """Read the bundled logo once per process for inline MIME attachments."""
    return Path(EMAIL_LOGO_PATH).read_bytes()


def smtp_configured(config: dict[str, Any]) -> bool:
    """Check whether an SMTP host and sender address are supplied.

    Args:
        config: Runtime settings containing ``SMTP_HOST`` and ``SMTP_FROM_EMAIL``.

    Returns:
        Whether both settings contain nonblank text; no connection or address
        validation is performed.
    """
    if not config.get("EMAIL_ENABLED", True):
        return False
    host = str(config.get("SMTP_HOST") or "").strip()
    from_email = str(config.get("SMTP_FROM_EMAIL") or "").strip()
    return bool(host and from_email)


def send_email(
    *,
    config: dict[str, Any],
    to_email: str,
    subject: str,
    text_body: str,
    log: logging.Logger | None = None,
    purpose: str = "account",
    severity: str = "info",
    action_url: str = "",
    action_label: str = "Open Coyote3",
) -> bool:
    """Send branded HTML and plain-text alternatives using the selected SMTP sender.

    Args:
        config: Validated runtime SMTP settings, including transport and sender.
        to_email: Recipient address resolved by the calling workflow.
        subject: Plain-text message subject.
        text_body: Plain-text message body.
        log: Optional workflow logger; defaults to the notification logger.
        purpose: Account, security, or broadcast sender identity.
        severity: Importance badge for both HTML and plain-text alternatives.
        action_url: Optional HTTP(S) action link.
        action_label: Text displayed on the HTML action button.

    Returns:
        Whether the SMTP server accepted the message. Missing configuration or
        transport failures return False; acceptance does not prove inbox delivery.

    Notes:
        TLS verifies the server certificate. Logs omit recipients and message content.
    """
    log = log or logger
    if not config.get("EMAIL_ENABLED", True):
        log.info("Email service disabled in application controls; email was not sent")
        emit_mail_metric("send_skipped", reason="email_disabled")
        return False
    if not smtp_configured(config):
        emit_mail_metric("send_skipped", reason="smtp_not_configured")
        log.info("SMTP not configured; email was not sent")
        return False

    host = str(config.get("SMTP_HOST")).strip()
    port = int(config.get("SMTP_PORT", 587) or 587)
    username = str(config.get("SMTP_USERNAME") or "").strip()
    password = str(config.get("SMTP_PASSWORD") or "")
    use_tls = bool(config.get("SMTP_USE_TLS", True))
    use_ssl = bool(config.get("SMTP_USE_SSL", False))
    from_email = str(config.get("SMTP_FROM_EMAIL")).strip()
    from_name = str(config.get("SMTP_FROM_NAME") or "Coyote3").strip()

    try:
        sender_key = {
            "account": "SMTP_FROM_EMAIL",
            "security": "SMTP_SECURITY_FROM_EMAIL",
            "broadcast": "SMTP_INFO_FROM_EMAIL",
        }[purpose]
        from_email = str(config.get(sender_key) or from_email).strip()
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = str(to_email).strip()
        msg["Reply-To"] = from_email
        msg["Auto-Submitted"] = "auto-generated"
        msg["X-Auto-Response-Suppress"] = "All"
        msg.set_content(
            f"[{severity.upper()}] {subject}\n\n{text_body}\n\n"
            "Automated Coyote3 message. This mailbox is not monitored; do not reply."
        )
        html_part = EmailMessage()
        html_part.set_content(
            render_email(
                subject=subject,
                text_body=text_body,
                severity=severity,
                environment=str(config.get("ENV_NAME") or ""),
                action_url=action_url,
                action_label=action_label,
            ),
            subtype="html",
        )
        html_part.add_related(
            _logo_bytes(),
            maintype="image",
            subtype="png",
            cid="<coyote3-logo>",
            disposition="inline",
        )
        msg.make_alternative()
        msg.attach(html_part)
        emit_mail_metric(
            "send_attempt",
            host=host,
            transport="ssl" if use_ssl else ("starttls" if use_tls else "plain"),
        )
        if use_ssl:
            with smtplib.SMTP_SSL(
                host, port, timeout=15, context=ssl.create_default_context()
            ) as server:
                if username:
                    server.login(username, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                if use_tls:
                    server.starttls(context=ssl.create_default_context())
                if username:
                    server.login(username, password)
                server.send_message(msg)
        emit_mail_metric("send_result", outcome="success", host=host)
        return True
    except Exception as exc:
        emit_mail_metric("send_result", outcome="failed", host=host, error=type(exc).__name__)
        log.warning("SMTP delivery failed error_type=%s", type(exc).__name__)
        return False
