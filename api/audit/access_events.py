"""Access-check audit event emitters."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import Request

from api.runtime import current_request_id

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


def request_id(request: Request | None) -> str:
    if request is not None:
        rid = (request.headers.get("X-Request-ID") or "").strip()
        if rid:
            return rid
    return current_request_id()


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
        "request_id": request_id(request),
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


def emit_mutation_event(
    *,
    request: Request,
    username: str,
    status_code: int,
    action: str,
    target: str,
    extra: dict | None = None,
) -> None:
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "api",
        "action": "mutation",
        "status": "ok" if 200 <= int(status_code) < 400 else "failed",
        "status_code": int(status_code),
        "method": request.method,
        "path": str(request.url.path),
        "ip": request_ip(request),
        "request_id": request_id(request),
        "username": username,
        "target": target,
        "mutation_action": action,
        "extra": extra or {},
    }
    _audit_logger.info(json.dumps(event, default=str))
