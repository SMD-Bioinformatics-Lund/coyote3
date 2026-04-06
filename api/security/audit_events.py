"""Access-check audit event emitters."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Request

from api.runtime_state import current_request_id
from shared.logging import emit_audit_event


def request_ip(request: Request | None) -> str:
    """Resolve the best-effort client IP address for a request.

    Args:
        request: Active request, when available.

    Returns:
        str: Client IP or ``"N/A"`` when unavailable.
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
    """Resolve the current request identifier.

    Args:
        request: Active request, when available.

    Returns:
        str: Request identifier from the request or runtime context.
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
    """Emit an audit event for an access-control decision.

    Args:
        status: Result of the access decision.
        reason: Human-readable explanation for the decision.
        request: Active request, when available.
        user_id: Authenticated user identifier.
        username: Authenticated username.
        role: Effective user role.
        permission: Required permission, when applicable.
        min_level: Minimum required access level.
        min_role: Minimum required role name.
        sample_id: Sample identifier associated with the check.
        extra: Additional structured metadata to emit.
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
    """Emit an audit event for a mutating API request.

    Args:
        request: Active request.
        username: Authenticated username.
        status_code: Final response status code.
        action: Mutation verb being recorded.
        target: Resource target for the mutation.
        extra: Additional structured metadata to emit.
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
    """Emit an audit event for a completed API request.

    Args:
        request: Active request.
        username: Authenticated username.
        status_code: Final response status code.
        duration_ms: End-to-end request duration in milliseconds.
        extra: Additional structured metadata to emit.
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
