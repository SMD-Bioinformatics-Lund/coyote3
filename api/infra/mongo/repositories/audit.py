"""Audit persistence, durable fallback and replay on the owning MongoDB client."""

import logging
from pathlib import Path
from typing import Any

from bson import ObjectId
from pymongo.errors import PyMongoError

from api.infra.mongo.repositories.audit_integrity import append_event
from api.infra.mongo.repositories.audit_outbox import AuditOutboxRepository
from api.infra.observability.audit_spool import AuditSpool


class AuditRepository:
    """Keep database writes and recovery transports outside audit event construction."""

    def __init__(
        self,
        collection: Any,
        *,
        spool_directory: Path | None = None,
        outboxes: tuple[AuditOutboxRepository, ...] = (),
        outbox_route: str | None = None,
    ) -> None:
        """Bind the destination, business outboxes and optional persistent retry volume.

        Args:
            collection: Audit destination with acknowledged write concern.
            spool_directory: Persistent fallback directory; None disables disk fallback.
            outboxes: Business database queues belonging to this deployment.
            outbox_route: Credential-independent destination namespace.
        """
        self.collection = collection
        self.spool = AuditSpool(spool_directory) if spool_directory is not None else None
        self.outboxes = outboxes
        self.outbox_route = outbox_route
        self.logger = logging.getLogger("coyote3.audit")

    def persist(self, document: dict[str, Any]) -> str | None:
        """Store a sanitized event, retaining failed inserts on the configured retry volume.

        Args:
            document: Redacted event with an explicit retention class. A stable ID
                is allocated once here when the application has not supplied one.

        Returns:
            Stable event ID when accepted by MongoDB or disk; None when MongoDB fails
            and no spool is configured.

        Raises:
            OSError: MongoDB and the configured retry volume are both unavailable.
        """
        document = dict(document)
        document.setdefault("_id", ObjectId())
        try:
            if document["retention_class"] == "traceability":
                return str(append_event(self.collection, document))
            result = self.collection.insert_one(document)
            if not result.acknowledged:
                raise PyMongoError("Audit inserts require acknowledged write concern")
            return str(result.inserted_id)
        except PyMongoError:
            if self.spool is None:
                self.logger.critical("Failed to persist audit event", exc_info=True)
                return None
            try:
                self.spool.persist(document)
            except OSError:
                self.logger.critical("Audit database and retry volume unavailable", exc_info=True)
                raise
            self.logger.critical(
                "Audit event queued for retry",
                extra={
                    "audit_event_id": str(document["_id"]),
                    "event_type": document["event_type"],
                },
            )
            return str(document["_id"])

    def replay_pending(self, *, environment: str) -> int:
        """Deliver bounded outbox and disk batches; retain failed database deliveries.

        Args:
            environment: Deployment source label attached to outbox events.

        Returns:
            Number of accepted events across all configured retry sources.
        """
        delivered = 0
        for outbox in self.outboxes:
            try:
                delivered += outbox.deliver(
                    self.collection, environment=environment, route=self.outbox_route
                )
            except PyMongoError:
                self.logger.error("Audit outbox delivery failed; events retained", exc_info=True)
        if self.spool is not None:
            delivered += self.spool.replay(self.collection)
        return delivered

    def recent_events(self, *, limit: int) -> dict[str, Any]:
        """Return newest stored events and the complete audit count.

        Args:
            limit: Positive event limit already bounded by the application service.

        Returns:
            Events ordered newest first and the collection's complete document count.
        """
        return {
            "events": list(self.collection.find({}).sort("occurred_at", -1).limit(limit)),
            "total": self.collection.count_documents({}),
        }
