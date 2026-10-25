"""Read committed activity for retry-safe notification delivery across database endpoints."""

from datetime import datetime
from hashlib import sha256
from typing import Any

from bson import ObjectId

from api.config.collections import load_collection_section
from api.config.operational_collections import OPERATIONAL_COLLECTIONS
from api.config.security import get_audit_events_collection_name


class NotificationActivityRepository:
    """Read audit events and knowledgebase releases without modifying either source."""

    @classmethod
    def from_store(cls, store: Any, *, config: dict) -> "NotificationActivityRepository":
        """Resolve configured source and destination collections on their owning clients.

        Args:
            store: Initialized repository store with independent database handles.
            config: Runtime settings containing collection mappings.

        Returns:
            Read-only activity source with a notification delivery lookup.
        """
        return cls(
            audit_collection=store.identity_db[get_audit_events_collection_name(config)],
            versions_collection=store.knowledgebase_db[
                load_collection_section("knowledgebase")["knowledgebase_versions_collection"]
            ],
            notifications=store.notification_repository.get_collection(),
        )

    def __init__(self, *, audit_collection: Any, versions_collection: Any, notifications: Any):
        """Bind explicitly selected source collections and the destination collection.

        Args:
            audit_collection: Identity database audit collection.
            versions_collection: Knowledgebase release registry.
            notifications: Application database notification collection.
        """
        self.audit = audit_collection
        self.versions = versions_collection
        self.notifications = notifications
        self.progress = notifications.database[
            OPERATIONAL_COLLECTIONS.notification_activity_progress
        ]
        self._pending_progress: dict[str, Any] | None = None

    def pending(self, *, since: datetime, environment: str, limit: int = 100) -> list[dict]:
        """Find undelivered committed events, including late audit-outbox arrivals.

        Args:
            since: Oldest event within the notification retention interval.
            environment: Deployment environment; excludes other deployments' audit events.
            limit: Scan budget, split between forward and reconciliation readers for each source.
                At least four records are scanned per call.

        Returns:
            Events without a notification bearing the same stable identifier.

        Notes:
            Separate reads support independent MongoDB servers. No cross-client session
            or cross-database lookup is used. Insert-only destination writes handle races.
        """
        query = {"occurred_at": {"$gte": since}, "source.environment": environment}
        state = self.progress.find_one({"_id": environment}) or {"_id": environment}
        result = []
        budget = max(1, limit // 4)
        events = self._scan_source(self.audit, query, "occurred_at", "audit", state, budget)
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
        events = [event for event in events if self._notifiable(event)]
        for release in releases:
            if release.get("status") not in {"active", "retired"}:
                continue
            identity = ObjectId(
                sha256(
                    f"knowledgebase:{release['_id']}:{release['published_at'].isoformat()}".encode()
                ).hexdigest()[:24]
            )
            events.append(
                {
                    "_id": identity,
                    "event_type": "knowledgebase.release.published",
                    "occurred_at": release["published_at"],
                    "resource": {
                        "type": "knowledgebase",
                        "id": str(release["_id"]),
                        "name": str(release.get("source") or release["_id"]),
                    },
                    "metadata": {"release": str(release.get("release") or "")},
                }
            )
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
    def _notifiable(event: dict[str, Any]) -> bool:
        """Select supported successful activity from a bounded source page.

        Args:
            event: Committed audit document, including outcome, operation and resource type.

        Returns:
            Whether the operation belongs to a supported activity-notification category.
        """
        if event.get("outcome") != "success":
            return False
        kind = event.get("event_type")
        return kind in {"report.saved", "knowledgebase.oncokb_public.refresh.completed"} or (
            kind == "api.mutation.succeeded"
            and (event.get("resource") or {}).get("type")
            in {
                "asp",
                "aspc",
                "assay_group",
                "diagnosis",
                "assay_diagnosis",
                "assay_setup",
                "genelist",
            }
        )

    def _scan_source(
        self, collection: Any, query: dict, timestamp: str, name: str, state: dict, budget: int
    ) -> list[dict]:
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
            self.progress.replace_one({"_id": state["_id"]}, state, upsert=True)
            self._pending_progress = None
