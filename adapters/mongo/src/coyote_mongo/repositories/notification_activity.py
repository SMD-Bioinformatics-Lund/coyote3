# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Read committed activity for retry-safe notification delivery across database endpoints."""

from collections.abc import Callable
from datetime import datetime
from hashlib import sha256
from typing import Any

from bson import ObjectId
from pymongo.change_stream import CollectionChangeStream

from coyote_mongo.config.collections import load_collection_section
from coyote_mongo.config.operational_collections import (
    OPERATIONAL_COLLECTIONS,
    get_audit_events_collection_name,
)
from coyote_mongo.config.settings import AuditContext
from coyote_mongo.repositories.mutations import write_with_audit

_ACTIVITY_EVENTS = ("report.saved", "knowledgebase.oncokb_public.refresh.completed")
_CONFIGURATION_TYPES = ("asp", "aspc", "assay_group", "diagnosis", "assay_diagnosis", "genelist")


class NotificationActivityRepository:
    """Read audit events and knowledgebase releases without modifying either source."""

    @classmethod
    def from_store(cls, store: Any, *, config: dict[str, Any]) -> "NotificationActivityRepository":
        """Resolve configured source and destination collections on their owning clients.

        Args:
            store: Initialized repository store with independent database handles.
            config: Runtime settings containing collection mappings.

        Returns:
            Read-only activity source with a notification delivery lookup.
        """
        return cls(
            audit_collection=store.identity_db[get_audit_events_collection_name(config)],
            operational_collection=store.identity_db[
                OPERATIONAL_COLLECTIONS.operational_audit_events
            ],
            versions_collection=store.knowledgebase_db[
                load_collection_section("knowledgebase")["knowledgebase_versions_collection"]
            ],
            notifications=store.notification_repository.get_collection(),
            context=store.app.audit,
        )

    def __init__(
        self,
        *,
        audit_collection: Any,
        operational_collection: Any,
        versions_collection: Any,
        notifications: Any,
        context: AuditContext,
    ):
        """Bind explicitly selected source collections and the destination collection.

        Args:
            audit_collection: Identity database audit collection.
            operational_collection: New operational events, separate from retained history.
            versions_collection: Knowledgebase release registry.
            notifications: Application database notification collection.
            context: Owning deployment's transactional audit identity.
        """
        self.audit = audit_collection
        self.operational = operational_collection
        self.versions = versions_collection
        self.notifications = notifications
        self.audit_context = context
        self.progress = notifications.database[
            OPERATIONAL_COLLECTIONS.notification_activity_progress
        ]
        self._pending_progress: dict[str, Any] | None = None

    def pending(
        self, *, since: datetime, environment: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Find undelivered committed events, including late audit-outbox arrivals.

        Args:
            since: Oldest event within the notification retention interval.
            environment: Deployment environment; excludes other deployments' audit events.
            limit: Scan budget, split between forward and reconciliation readers for each source.
                At least six records are scanned per call.

        Returns:
            Events without a notification bearing the same stable identifier.

        Notes:
            Separate reads support independent MongoDB servers. No cross-client session
            or cross-database lookup is used. Insert-only destination writes handle races.
        """
        query = {
            "occurred_at": {"$gte": since},
            "source.environment": environment,
            "category": {"$ne": "database_mutation"},
        }
        state = self.progress.find_one({"_id": environment}) or {"_id": environment}
        result = []
        budget = max(1, limit // 6)
        events = self._scan_source(self.audit, query, "occurred_at", "audit", state, budget)
        events.extend(
            self._scan_source(
                self.operational, query, "occurred_at", "operational_audit", state, budget
            )
        )
        releases = self._scan_source(
            self.versions,
            {
                "published_at": {"$gte": since},
            },
            "published_at",
            "knowledgebase",
            state,
            budget,
        )
        events = [
            event
            for event in events
            if event.get("outcome") == "success"
            and (
                event.get("event_type") in _ACTIVITY_EVENTS
                or event.get("event_type") == "api.mutation.succeeded"
                and (event.get("resource") or {}).get("type") in _CONFIGURATION_TYPES
            )
        ]
        for release in releases:
            if release.get("status") not in {"active", "retired"}:
                continue
            events.append(self.release_event(release))
        delivered = {
            row["_id"]
            for row in self.notifications.find(
                {"_id": {"$in": [event["_id"] for event in events]}}, {"_id": 1}
            )
        }
        seen = set(delivered)
        for event in events:
            if event["_id"] not in seen:
                result.append(event)
                seen.add(event["_id"])
        self._pending_progress = state
        return result

    @staticmethod
    def release_event(release: dict[str, Any]) -> dict[str, Any]:
        """Use the same release identity for live updates and scheduled reconciliation."""
        identity = f"knowledgebase:{release['_id']}:{release['published_at'].isoformat()}"
        return {
            "_id": ObjectId(sha256(identity.encode()).hexdigest()[:24]),
            "event_type": "knowledgebase.release.published",
            "occurred_at": release["published_at"],
            "resource": {
                "type": "knowledgebase",
                "id": str(release["_id"]),
                "name": str(release.get("source") or release["_id"]),
            },
            "metadata": {"release": str(release.get("release") or "")},
        }

    def live_sources(
        self, environment: str
    ) -> dict[str, Callable[[], CollectionChangeStream[dict[str, Any]]]]:
        """Return collection-specific change streams for committed inbox and activity writes."""

        def watch(
            collection: Any, match: dict[str, Any], fields: dict[str, Any], *, updates: bool = False
        ) -> Callable[[], CollectionChangeStream[dict[str, Any]]]:
            pipeline = [{"$match": match}, {"$project": {"_id": 1, **fields}}]
            return lambda: collection.watch(
                pipeline,
                full_document="updateLookup" if updates else None,
                max_await_time_ms=1000,
            )

        audit = {
            "operationType": "insert",
            "fullDocument.source.environment": environment,
            "fullDocument.outcome": "success",
            "fullDocument.category": {"$ne": "database_mutation"},
            "$or": [
                {"fullDocument.event_type": {"$in": _ACTIVITY_EVENTS}},
                {
                    "fullDocument.event_type": "api.mutation.succeeded",
                    "fullDocument.resource.type": {"$in": _CONFIGURATION_TYPES},
                },
            ],
        }
        fields = {
            key: "$fullDocument." + key
            for key in (
                "_id",
                "event_type",
                "occurred_at",
                "resource",
                "metadata",
                "actor",
            )
        }
        # Preserve the MongoDB resume token in _id; the business event lives under document.
        audit_fields = {"document": fields}
        db = self.notifications.database
        return {
            "inbox": watch(
                self.notifications,
                {
                    "$or": [
                        {"operationType": {"$in": ["insert", "replace"]}},
                        {
                            "operationType": "update",
                            "updateDescription.updatedFields.withdrawn_on": {"$exists": True},
                        },
                    ],
                },
                {"audience": "$fullDocument.audience", "recipients": "$fullDocument.recipients"},
                updates=True,
            ),
            "audit": watch(self.audit, audit, audit_fields),
            "operational": watch(self.operational, audit, audit_fields),
            "report": watch(
                db[OPERATIONAL_COLLECTIONS.audit_outbox],
                {
                    "operationType": "insert",
                    "fullDocument.route": self.audit_context.route,
                    "fullDocument.event.source.environment": environment,
                    "fullDocument.event.event_type": "report.saved",
                    "fullDocument.event.outcome": "success",
                },
                {"document": {key: "$fullDocument.event." + key for key in fields}},
            ),
            "release": watch(
                self.versions,
                {
                    "operationType": {"$in": ["insert", "update", "replace"]},
                    "fullDocument.status": {"$in": ["active", "retired"]},
                    "fullDocument.published_at": {"$type": "date"},
                },
                {
                    "document": {
                        key: "$fullDocument." + key
                        for key in (
                            "_id",
                            "published_at",
                            "release",
                            "source",
                        )
                    }
                },
                updates=True,
            ),
        }

    def _scan_source(
        self,
        collection: Any,
        query: dict[str, Any],
        timestamp: str,
        name: str,
        state: dict[str, Any],
        budget: int,
    ) -> list[dict[str, Any]]:
        """Read bounded forward and cyclic reconciliation pages using stable compound cursors.

        Reconciliation catches delayed outbox events older than the forward watermark.
        It advances a page each poll and restarts at the retention boundary after EOF.
        Source documents remain immutable; cursors are acknowledged only after delivery.

        Args:
            collection: Source collection on its owning MongoDB client.
            query: Deployment/retention predicate applied before cursor positions.
            timestamp: Stored BSON datetime field used for primary ordering.
            name: Source key separating its two cursor lanes in progress state.
            state: Pending environment-scoped cursor document, updated only in memory here.
            budget: Maximum records per lane; both lanes may read the same records.

        Returns:
            At most twice the budget in source rows, in lane/page order.
        """
        rows = []
        for lane in ("forward", "reconcile"):
            key = f"{name}_{lane}"
            position = state.get(key)
            selector = query
            if position:
                selector = {
                    "$and": [
                        query,
                        {
                            "$or": [
                                {timestamp: {"$gt": position["time"]}},
                                {
                                    timestamp: position["time"],
                                    "$expr": {
                                        "$gt": ["$_id", {"$literal": position["id"]}],
                                    },
                                },
                            ]
                        },
                    ]
                }
            batch = list(collection.find(selector).sort([(timestamp, 1), ("_id", 1)]).limit(budget))
            rows.extend(batch)
            if batch:
                state[key] = {"time": batch[-1][timestamp], "id": batch[-1]["_id"]}
            if len(batch) < budget and lane == "reconcile":
                state[key] = None
        return rows

    def acknowledge(self) -> None:
        """Persist scan positions only after all returned events have been written.

        Retrying a failed write replays the page using stable notification identifiers.
        Concurrent deliveries may move a cursor backwards, causing harmless replay;
        no cursor advances past an unprocessed event.
        """
        if self._pending_progress is not None:
            state = self._pending_progress
            write_with_audit(
                self.progress,
                "replace_one",
                {"_id": state["_id"]},
                state,
                upsert=True,
                context=self.audit_context,
            )
            self._pending_progress = None
