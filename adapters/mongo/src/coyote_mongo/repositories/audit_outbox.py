# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Transaction-owned audit events and idempotent cross-database delivery."""

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from coyote.application.audit.metadata import safe_audit_metadata
from coyote.application.common.execution_context import current_user, current_username
from coyote.application.common.request_context import current_request_context
from coyote.config.policy import get_runtime_environment
from coyote.domain.common.diagnostics import redact_diagnostics
from pymongo.write_concern import WriteConcern

from coyote_mongo.config.endpoints import MongoEndpoint, mongo_uri
from coyote_mongo.config.operational_collections import OPERATIONAL_COLLECTIONS
from coyote_mongo.config.settings import AuditContext
from coyote_mongo.repositories.audit_integrity import append_event
from coyote_mongo.transactions import run_transaction


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
    return AuditContext.for_endpoint(get_runtime_environment(config), endpoint).route


def insert_audited(collection: Any, document: dict, *, context: AuditContext) -> Any:
    """Insert a clinical configuration and its receipt atomically.

    Args:
        collection: Owning business collection.
        document: Validated configuration; source data is copied before insertion.
        context: Explicit deployment identity for the committed receipt.

    Returns:
        Acknowledged PyMongo insert result for repository-level conversion.
    """

    def insert(session):
        """Insert both records using the caller's owning session."""
        result = collection.insert_one(dict(document), session=session)
        enqueue_audit(
            collection.database,
            session,
            context=context,
            event_type="configuration.created",
            resource_type=collection.name,
            resource_id=result.inserted_id,
            actor=document.get("created_by"),
        )
        return result

    return run_transaction(collection.database.client, insert)


def update_audited(collection: Any, selector: dict, update: dict, *, context: AuditContext) -> Any:
    """Update a clinical configuration and record its changed fields in one commit.

    Args:
        collection: Owning business collection.
        selector: Exact identity and expected state to update.
        update: Server-built MongoDB update; values are not copied to the receipt.
        context: Explicit deployment identity for the committed receipt.

    Returns:
        PyMongo update result; unmatched writes do not create audit receipts.
    """

    update = {
        **update,
        "$set": {**update.get("$set", {}), "updated_by": current_username("") or None},
    }

    def change(session):
        """Resolve the resource identity inside the same transaction as its update."""
        previous = collection.find_one(selector, {"_id": 1}, session=session)
        result = collection.update_one(selector, update, session=session)
        if result.modified_count:
            enqueue_audit(
                collection.database,
                session,
                context=context,
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
    context: AuditContext,
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
        context: Host-selected deployment identity; no environment variables are read.
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
    request = current_request_context()
    route = context.route
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
                "application": "coyote4",
                "environment": context.environment,
                "database": database.name,
                "request_id": request.request_id if request else None,
                "method": request.method if request else None,
                "path": request.path if request else None,
                "client_ip": request.client_ip if request else None,
                "user_agent": request.user_agent[:500] if request and request.user_agent else None,
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

    def deliver(self, destination: Any, *, environment: str, route: str, limit: int = 100) -> int:
        """Copy a bounded batch, deleting only after durable destination acknowledgement.

        Args:
            destination: Central audit collection, possibly on a different MongoClient.
            environment: Deployment environment recorded on delivered events.
            limit: Maximum number of pending events, clamped between one and 1000.
            route: Explicit owning deployment routing hash.

        Returns:
            Number of acknowledged deliveries; concurrent workers may count the same ID.

        Raises:
            PyMongoError: Delivery or deletion failed; remaining events stay queued.

        Notes:
            Insert-only upserts preserve existing audit events. Crashes after delivery
            but before deletion cause replay with the same ID, not duplicate records.
        """
        if not route:
            raise ValueError("Audit outbox delivery requires an explicit deployment route")
        target = destination.with_options(write_concern=WriteConcern("majority", j=True))
        delivered = 0
        selector = {
            "route": route,
            "event.source.environment": environment,
        }
        for pending in (
            self.collection.find(selector).sort("_id", 1).limit(max(1, min(limit, 1000)))
        ):
            event = pending["event"]
            append_event(target, event)
            self.collection.delete_one({"_id": pending["_id"]})
            delivered += 1
        return delivered
