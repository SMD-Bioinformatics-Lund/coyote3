"""Minimal SMTP notification helper for auth/user lifecycle emails."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from api.runtime import app as runtime_app


def smtp_configured() -> bool:
    host = str(runtime_app.config.get("SMTP_HOST") or "").strip()
    from_email = str(runtime_app.config.get("SMTP_FROM_EMAIL") or "").strip()
    return bool(host and from_email)


def send_email(*, to_email: str, subject: str, text_body: str) -> bool:
    """Send a plain-text email using configured SMTP settings.

    Returns ``False`` when SMTP is not configured or when sending fails.
    """
    if not smtp_configured():
        runtime_app.logger.info(
            "SMTP not configured. Skipping email send to=%s subject=%s", to_email, subject
        )
        return False

    host = str(runtime_app.config.get("SMTP_HOST")).strip()
    port = int(runtime_app.config.get("SMTP_PORT", 587) or 587)
    username = str(runtime_app.config.get("SMTP_USERNAME") or "").strip()
    password = str(runtime_app.config.get("SMTP_PASSWORD") or "")
    use_tls = bool(runtime_app.config.get("SMTP_USE_TLS", True))
    use_ssl = bool(runtime_app.config.get("SMTP_USE_SSL", False))
    from_email = str(runtime_app.config.get("SMTP_FROM_EMAIL")).strip()
    from_name = str(runtime_app.config.get("SMTP_FROM_NAME") or "Coyote3").strip()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = str(to_email).strip()
    msg.set_content(text_body)

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(host, port, timeout=15) as server:
                if username:
                    server.login(username, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                if use_tls:
                    server.starttls()
                if username:
                    server.login(username, password)
                server.send_message(msg)
        return True
    except Exception as exc:
        runtime_app.logger.warning(
            "Failed to send email to=%s subject=%s err=%s", to_email, subject, exc
        )
        return False
