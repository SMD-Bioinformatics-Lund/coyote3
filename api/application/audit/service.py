"""Mongo-backed append-only audit event service."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from bson import ObjectId
from pymongo.errors import PyMongoError

from api.infra.mongo.repositories.audit_outbox import AuditOutboxRepository
from api.infra.observability.audit import safe_audit_metadata
from api.infra.observability.audit_spool import AuditSpool
from api.infra.observability.logging import current_request_context
from api.infra.observability.redaction import redact_diagnostics, redact_text

AuditSeverity = Literal["info", "warning", "error", "critical"]
AuditOutcome = Literal["success", "failure", "denied"]
AuditRetentionClass = Literal["operational", "traceability"]


class AuditService:
    """Persist security and business audit events as MongoDB documents."""

    def __init__(
        self,
        collection: Any,
        *,
        retention_days: int,
        environment: str,
        spool_directory: Path | None = None,
        outboxes: tuple[AuditOutboxRepository, ...] = (),
        outbox_route: str | None = None,
    ) -> None:
        """Configure audit storage and operational event expiry.

        Args:
            collection: MongoDB collection accepting audit inserts and recent-event queries.
            retention_days: Operational retention in days, clamped to at least 30.
            environment: Source environment label; falsey values use development.
            spool_directory: Persistent retry directory; None disables disk fallback.
            outboxes: Queues in business databases owned by this deployment.
            outbox_route: Credential-independent destination namespace for queue isolation.
        """
        self.collection = collection
        self.retention_days = max(int(retention_days), 30)
        self.environment = str(environment or "development")
        self.logger = logging.getLogger("coyote3.audit")
        self.spool = AuditSpool(spool_directory) if spool_directory is not None else None
        self.outboxes = outboxes
        self.outbox_route = outbox_route

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
        retention_class: AuditRetentionClass = "operational",
    ) -> str | None:
        """Append an event, spooling MongoDB failures when a persistent directory is configured.

        Args:
            event_type: Stable dotted operation identifier.
            message: Diagnostic summary, limited to 500 characters in storage.
            severity: Operational log severity.
            category: Event family used in administrative filtering.
            outcome: Whether the operation succeeded, failed or was denied.
            actor: Authenticated identity or login; None records anonymous.
            provider: Authentication provider override, when known.
            resource_type: Kind of affected resource, or None.
            resource_id: Stable affected resource identifier, or None.
            resource_name: Optional human-readable resource name.
            tags: Searchable event labels, deduplicated and lowercased.
            metadata: Bounded, credential-redacted diagnostic context.
            retention_class: Operational events expire; traceability events do not.

        Returns:
            Event ID when MongoDB or the retry spool accepted it; None if no spool is configured.

        Raises:
            OSError: Both MongoDB and the configured retry volume are unavailable.

        Notes:
            This operation is not atomic with writes to a separate business database.
        """
        now = datetime.now(timezone.utc)
        request = current_request_context()
        actor_doc = self._actor_document(actor, provider=provider)
        document = {
            "_id": ObjectId(),
            "occurred_at": now,
            "retention_class": retention_class,
            "immutable": retention_class == "traceability",
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
        if retention_class == "operational":
            document["expires_at"] = now + timedelta(days=self.retention_days)
        document = redact_diagnostics(document)
        try:
            result = self.collection.insert_one(document)
            if not result.acknowledged:
                raise PyMongoError("Audit inserts require acknowledged write concern")
            event_id = result.inserted_id
        except PyMongoError:
            if self.spool is not None:
                try:
                    self.spool.persist(document)
                except OSError:
                    self.logger.critical(
                        "Audit database and retry volume unavailable", exc_info=True
                    )
                    raise
                self.logger.critical(
                    "Audit event queued for retry",
                    extra={
                        "audit_event_id": str(document["_id"]),
                        "event_type": event_type,
                    },
                )
                return str(document["_id"])
            self.logger.critical(
                "Failed to persist audit event",
                exc_info=True,
                extra={"event_type": event_type, "audit_severity": severity},
            )
            return None
        self.logger.info(
            redact_text(message),
            extra={
                "audit_event_id": str(event_id),
                "event_type": event_type,
                "audit_severity": severity,
                "outcome": outcome,
            },
        )
        return str(event_id)

    def replay_pending(self) -> int:
        """Deliver bounded database-outbox and filesystem batches and return the total count.

        Notes:
            Database delivery failures retain pending events and are logged. Other
            configured queues are still attempted; filesystem I/O failures propagate.
        """
        delivered = 0
        for outbox in self.outboxes:
            try:
                delivered += outbox.deliver(
                    self.collection, environment=self.environment, route=self.outbox_route
                )
            except PyMongoError:
                self.logger.error("Audit outbox delivery failed; events retained", exc_info=True)
        if self.spool is not None:
            delivered += self.spool.replay(self.collection)
        return delivered

    def recent_events(self, *, limit: int) -> dict[str, Any]:
        """Return recent audit events and total event count."""
        bounded_limit = max(1, min(int(limit or 200), 1000))
        events = list(self.collection.find({}).sort("occurred_at", -1).limit(bounded_limit))
        return {"events": events, "total": self.collection.count_documents({})}

    @staticmethod
    def _actor_document(actor: Any | str | None, *, provider: str | None) -> dict[str, Any]:
        """Project an actor object or login into audit identity fields.

        Args:
            actor: Login string, object with identity attributes, or None for anonymous.
            provider: Authentication provider override; objects supply auth_type if falsey.

        Returns:
            Username, full name, role list, and provider without unrelated actor data.
        """
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
