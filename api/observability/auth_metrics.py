"""Lightweight auth/mail observability emitters.

This module intentionally avoids external metrics dependencies and emits
structured log lines that can be scraped by centralized logging systems.
"""

from __future__ import annotations

from typing import Any

from api.runtime import app as runtime_app


def _normalize_label(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "unknown"
    # Keep labels compact and parser-safe.
    return text.replace(" ", "_").replace("=", ":")[:64]


def emit_auth_metric(metric: str, **labels: Any) -> None:
    """Emit a normalized authentication metric log line."""
    parts = [f"event={_normalize_label(metric)}"]
    for key, value in sorted(labels.items()):
        parts.append(f"{_normalize_label(key)}={_normalize_label(value)}")
    runtime_app.logger.info("auth_metric %s", " ".join(parts))


def emit_mail_metric(metric: str, **labels: Any) -> None:
    """Emit a normalized email-delivery metric log line."""
    parts = [f"event={_normalize_label(metric)}"]
    for key, value in sorted(labels.items()):
        parts.append(f"{_normalize_label(key)}={_normalize_label(value)}")
    runtime_app.logger.info("mail_metric %s", " ".join(parts))
