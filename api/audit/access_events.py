"""Access-check audit event emitters."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Request

from api.runtime import current_request_id
from shared.logging import emit_audit_event


def request_ip(request: Request | None) -> str:
    """Request ip.

    Args:
        request (Request | None): Value for ``request``.

    Returns:
        str: The function result.
    """
    if request is None:
        return "N/A"
    forwarded_for = (request.headers.get("X-Forwarded-For") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or "N/A"
    if request.client and request.client.host:
        return str(request.client.host)
    return "N/A"


def request_id(request: Request | None) -> str:
    """Request id.

    Args:
        request (Request | None): Value for ``request``.

    Returns:
        str: The function result.
    """
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
    """Emit access event.

    Args:
        status (str): Value for ``status``.
        reason (str): Value for ``reason``.
        request (Request | None): Value for ``request``.
        user_id (str | None): Value for ``user_id``.
        username (str | None): Value for ``username``.
        role (str | None): Value for ``role``.
        permission (str | None): Value for ``permission``.
        min_level (int | None): Value for ``min_level``.
        min_role (str | None): Value for ``min_role``.
        sample_id (str | None): Value for ``sample_id``.
        extra (dict | None): Value for ``extra``.

    Returns:
        None.
    """
    normalized_status = (
        "failed" if status == "denied" else ("success" if status in {"allowed", "ok"} else status)
    )
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "method": request.method if request else None,
        "path": str(request.url.path) if request else None,
        "ip": request_ip(request),
        "request_id": request_id(request),
        "user": username or user_id,
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
    emit_audit_event(
        source="api",
        action="access_check",
        status=normalized_status,
        severity="warning" if normalized_status == "failed" else "info",
        **event,
    )


def emit_mutation_event(
    *,
    request: Request,
    username: str,
    status_code: int,
    action: str,
    target: str,
    extra: dict | None = None,
) -> None:
    """Emit mutation event.

    Args:
        request (Request): Value for ``request``.
        username (str): Value for ``username``.
        status_code (int): Value for ``status_code``.
        action (str): Value for ``action``.
        target (str): Value for ``target``.
        extra (dict | None): Value for ``extra``.

    Returns:
        None.
    """
    derived_status = (
        "error" if int(status_code) >= 500 else ("failed" if int(status_code) >= 400 else "success")
    )
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status_code": int(status_code),
        "method": request.method,
        "path": str(request.url.path),
        "ip": request_ip(request),
        "request_id": request_id(request),
        "user": username,
        "username": username,
        "target": target,
        "mutation_action": action,
        "extra": extra or {},
    }
    emit_audit_event(
        source="api",
        action="mutation",
        status=derived_status,
        severity=(
            "error"
            if derived_status == "error"
            else ("warning" if derived_status == "failed" else "info")
        ),
        **event,
    )


def emit_request_event(
    *,
    request: Request,
    username: str,
    status_code: int,
    duration_ms: float,
    extra: dict | None = None,
) -> None:
    """Emit request event.

    Args:
        request (Request): Value for ``request``.
        username (str): Value for ``username``.
        status_code (int): Value for ``status_code``.
        duration_ms (float): Value for ``duration_ms``.
        extra (dict | None): Value for ``extra``.

    Returns:
        None.
    """
    derived_status = (
        "error" if int(status_code) >= 500 else ("failed" if int(status_code) >= 400 else "success")
    )
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status_code": int(status_code),
        "duration_ms": round(float(duration_ms), 2),
        "method": request.method,
        "path": str(request.url.path),
        "ip": request_ip(request),
        "request_id": request_id(request),
        "user": username,
        "username": username,
        "extra": extra or {},
    }
    emit_audit_event(
        source="api",
        action="request",
        status=derived_status,
        severity=(
            "error"
            if derived_status == "error"
            else ("warning" if derived_status == "failed" else "info")
        ),
        **event,
    )
