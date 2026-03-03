"""Access-check audit event emitters."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging

from fastapi import Request

_audit_logger = logging.getLogger("audit")


def request_ip(request: Request | None) -> str:
    if request is None:
        return "N/A"
    forwarded_for = (request.headers.get("X-Forwarded-For") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or "N/A"
    if request.client and request.client.host:
        return str(request.client.host)
    return "N/A"


def emit_access_event(
    *,
    status: str,
    reason: str,
    request: Request | None = None,
    user_id: str | None = None,
    username: str | None = None,
    role: str | None = None,
    permission: str | None = None,
    min_level: int | None = None,
    min_role: str | None = None,
    sample_id: str | None = None,
    extra: dict | None = None,
) -> None:
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "api",
        "action": "access_check",
        "status": status,
        "reason": reason,
        "method": request.method if request else None,
        "path": str(request.url.path) if request else None,
        "ip": request_ip(request),
        "user_id": user_id,
        "username": username,
        "role": role,
        "sample_id": str(sample_id) if sample_id is not None else None,
        "required": {
            "permission": permission,
            "min_level": min_level,
            "min_role": min_role,
        },
        "extra": extra or {},
    }
    payload = json.dumps(event, default=str)
    if status == "denied":
        _audit_logger.warning(payload)
    else:
        _audit_logger.info(payload)
