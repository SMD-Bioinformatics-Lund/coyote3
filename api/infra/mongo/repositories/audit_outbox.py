"""Transaction-owned audit events and idempotent cross-database delivery."""

import os
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from bson import ObjectId
from pymongo.write_concern import WriteConcern

from api.config.contracts.application import OPERATIONAL_COLLECTIONS
from api.config.mongo import MongoEndpoint, mongo_uri
from api.config.security import get_runtime_environment
from api.infra.mongo.transactions import run_transaction
from api.infra.observability.audit import safe_audit_metadata
from api.infra.observability.logging import current_request_context
from api.infra.observability.redaction import redact_diagnostics
from api.infra.request_context import current_user, current_username


def audit_route(config: Any) -> str:
    """Identify the owning deployment without storing credentials in shared queues.

    Args:
        config: Runtime or environment configuration with identity URI and database name.

    Returns:
        Hash of environment and credential-independent identity MongoDB namespace.

    Raises:
        RuntimeError: Identity connection settings are missing.
    """
    database = str(config.get("IDENTITY_DB") or "").strip()
    if not database:
        raise RuntimeError("IDENTITY_DB must be configured for transactional audit routing")
    endpoint = MongoEndpoint(mongo_uri(config, "identity"), database)
    return sha256(repr((get_runtime_environment(config), endpoint.namespace)).encode()).hexdigest()


def insert_audited(collection: Any, document: dict) -> Any:
    """Insert a clinical configuration and its receipt atomically.

    Args:
        collection: Owning business collection.
        document: Validated configuration; source data is copied before insertion.

    Returns:
        Acknowledged PyMongo insert result for repository-level conversion.
    """

    def insert(session):
        """Insert both records using the caller's owning session."""
        result = collection.insert_one(dict(document), session=session)
        enqueue_audit(
            collection.database,
            session,
            event_type="configuration.created",
            resource_type=collection.name,
            resource_id=result.inserted_id,
            actor=document.get("created_by"),
        )
        return result

    return run_transaction(collection.database.client, insert)


def update_audited(collection: Any, selector: dict, update: dict) -> Any:
    """Update a clinical configuration and record its changed fields in one commit.

    Args:
        collection: Owning business collection.
        selector: Exact identity and expected state to update.
        update: Server-built MongoDB update; values are not copied to the receipt.

    Returns:
        PyMongo update result; unmatched writes do not create audit receipts.
    """

    def change(session):
        """Resolve the resource identity inside the same transaction as its update."""
        previous = collection.find_one(selector, {"_id": 1}, session=session)
        result = collection.update_one(selector, update, session=session)
        if result.modified_count:
            enqueue_audit(
                collection.database,
                session,
                event_type="configuration.updated",
                resource_type=collection.name,
                resource_id=previous["_id"],
                metadata={"fields": sorted(update.get("$set", {}))},
            )
        return result

    return run_transaction(collection.database.client, change)


def enqueue_audit(
    database: Any,
    session: Any,
    *,
    event_type: str,
    resource_type: str,
    resource_id: Any,
    actor: str | None = None,
    metadata: dict | None = None,
    category: str = "business_transaction",
    resource_name: str | None = None,
) -> str:
    """Stage a traceability event in the transaction that owns the business write.

    Args:
        database: Database containing the changed business documents.
        session: Active transaction from this database's client, never a remote session.
        event_type: Stable operation name describing the committed change.
        resource_type: Collection or domain resource affected by the operation.
        resource_id: Stable resource ID, or batch identity.
        actor: Explicit actor for background operations; otherwise the current username.
        metadata: Bounded diagnostic facts, not clinical document contents or credentials.
        category: Administrative audit filter category; defaults to business_transaction.
        resource_name: Optional display identity, without copying clinical narrative.

    Returns:
        Stable event ID shared by the outbox row and eventual central audit record.

    Raises:
        ValueError: No active transaction, or a session from another client.
        PyMongoError: Staging fails; the owning transaction must abort.

    Notes:
        No central-database, filesystem or network integration is invoked here.
        Transaction retries discard events from aborted attempts along with business writes.
    """
    if session is None or not session.in_transaction or session.client is not database.client:
        raise ValueError("Audit outbox requires the owning database's active transaction")
    context = current_request_context()
    route = audit_route(os.environ)
    identity = ObjectId()
    username = actor or current_username()
    user = current_user() if username == current_username() else None
    event = redact_diagnostics(
        {
            "_id": identity,
            "occurred_at": datetime.now(timezone.utc),
            "retention_class": "traceability",
            "immutable": True,
            "severity": "info",
            "category": category,
            "event_type": event_type,
            "message": f"Committed {event_type}",
            "outcome": "success",
            "actor": {
                "username": username,
                "fullname": getattr(user, "fullname", None),
                "roles": list(getattr(user, "roles", []) or []),
                "provider": getattr(user, "auth_type", None),
            },
            "resource": {"type": resource_type, "id": str(resource_id), "name": resource_name},
            "source": {
                "application": "coyote3",
                "environment": get_runtime_environment(os.environ),
                "database": database.name,
                "request_id": context.request_id if context else None,
                "method": context.method if context else None,
                "path": context.path if context else None,
                "client_ip": context.client_ip if context else None,
                "user_agent": context.user_agent[:500] if context and context.user_agent else None,
            },
            "tags": sorted({"transactional_outbox", *event_type.split(".", 1)}),
            "metadata": safe_audit_metadata(metadata or {}),
        }
    )
    database[OPERATIONAL_COLLECTIONS.audit_outbox].insert_one(
        {"_id": identity, "route": route, "event": event},
        session=session,
    )
    return str(identity)


class AuditOutboxRepository:
    """Deliver transaction-owned events without sharing sessions between MongoDB services."""

    def __init__(self, database: Any) -> None:
        """Bind an owning database's queue with majority-acknowledged deletions.

        Args:
            database: Configured business database; pending rows have no TTL.
        """
        self.collection = database[OPERATIONAL_COLLECTIONS.audit_outbox].with_options(
            write_concern=WriteConcern("majority", j=True)
        )

    def deliver(
        self, destination: Any, *, environment: str, limit: int = 100, route: str | None = None
    ) -> int:
        """Copy a bounded batch, deleting only after durable destination acknowledgement.

        Args:
            destination: Central audit collection, possibly on a different MongoClient.
            environment: Deployment environment recorded on delivered events.
            limit: Maximum number of pending events, clamped between one and 1000.
            route: Owning deployment's routing hash; defaults to current process configuration.

        Returns:
            Number of acknowledged deliveries; concurrent workers may count the same ID.

        Raises:
            PyMongoError: Delivery or deletion failed; remaining events stay queued.

        Notes:
            Insert-only upserts preserve existing audit events. Crashes after delivery
            but before deletion cause replay with the same ID, not duplicate records.
        """
        target = destination.with_options(write_concern=WriteConcern("majority", j=True))
        delivered = 0
        selector = {
            "route": route or audit_route(os.environ),
            "event.source.environment": environment,
        }
        for pending in (
            self.collection.find(selector).sort("_id", 1).limit(max(1, min(limit, 1000)))
        ):
            event = pending["event"]
            target.update_one({"_id": event["_id"]}, {"$setOnInsert": event}, upsert=True)
            self.collection.delete_one({"_id": pending["_id"]})
            delivered += 1
        return delivered
