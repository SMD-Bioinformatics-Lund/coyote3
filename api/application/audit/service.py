"""Mongo-backed append-only audit event service."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pymongo.errors import PyMongoError

from api.infra.observability.audit import safe_audit_metadata
from api.infra.observability.logging import current_request_context

AuditSeverity = Literal["info", "warning", "error", "critical"]
AuditOutcome = Literal["success", "failure", "denied"]


class AuditService:
    """Persist security and business audit events as MongoDB documents."""

    def __init__(self, collection: Any, *, retention_days: int, environment: str) -> None:
        self.collection = collection
        self.retention_days = max(int(retention_days), 30)
        self.environment = str(environment or "development")
        self.logger = logging.getLogger("coyote3.audit")

    def record(
        self,
        event_type: str,
        message: str,
        *,
        severity: AuditSeverity = "info",
        category: str,
        outcome: AuditOutcome = "success",
        actor: Any | str | None = None,
        provider: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        resource_name: str | None = None,
        tags: list[str] | tuple[str, ...] = (),
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """Append one sanitized audit event and return its id when persisted."""
        now = datetime.now(timezone.utc)
        request = current_request_context()
        actor_doc = self._actor_document(actor, provider=provider)
        document = {
            "occurred_at": now,
            "expires_at": now + timedelta(days=self.retention_days),
            "severity": severity,
            "category": category.strip().lower(),
            "event_type": event_type.strip().lower(),
            "message": str(message)[:500],
            "outcome": outcome,
            "actor": actor_doc,
            "resource": {
                "type": resource_type,
                "id": str(resource_id) if resource_id is not None else None,
                "name": resource_name,
            },
            "source": {
                "application": "coyote3",
                "environment": self.environment,
                "request_id": request.request_id if request else None,
                "client_ip": request.client_ip if request else None,
                "method": request.method if request else None,
                "path": request.path if request else None,
                "user_agent": request.user_agent[:500] if request and request.user_agent else None,
            },
            "tags": sorted({str(tag).strip().lower() for tag in tags if str(tag).strip()}),
            "metadata": safe_audit_metadata(metadata or {}),
        }
        try:
            event_id = self.collection.insert_one(document).inserted_id
        except PyMongoError:
            self.logger.critical(
                "Failed to persist audit event",
                exc_info=True,
                extra={"event_type": event_type, "audit_severity": severity},
            )
            return None
        self.logger.info(
            message,
            extra={
                "audit_event_id": str(event_id),
                "event_type": event_type,
                "audit_severity": severity,
                "outcome": outcome,
            },
        )
        return str(event_id)

    def recent_events(self, *, limit: int) -> dict[str, Any]:
        """Return recent audit events and total event count."""
        bounded_limit = max(1, min(int(limit or 200), 1000))
        events = list(self.collection.find({}).sort("occurred_at", -1).limit(bounded_limit))
        return {"events": events, "total": self.collection.count_documents({})}

    @staticmethod
    def _actor_document(actor: Any | str | None, *, provider: str | None) -> dict[str, Any]:
        if actor is None:
            return {"username": "anonymous", "fullname": None, "roles": [], "provider": provider}
        if isinstance(actor, str):
            return {
                "username": actor or "anonymous",
                "fullname": None,
                "roles": [],
                "provider": provider,
            }
        return {
            "username": getattr(actor, "username", None)
            or getattr(actor, "id", None)
            or "anonymous",
            "fullname": getattr(actor, "fullname", None),
            "roles": list(getattr(actor, "roles", []) or []),
            "provider": provider or getattr(actor, "auth_type", None),
        }
