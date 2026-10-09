"""Read committed activity for retry-safe notification delivery across database endpoints."""

from datetime import datetime
from hashlib import sha256
from itertools import islice
from typing import Any

from bson import ObjectId

from api.config.loaders.collections import load_collection_section
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

    def pending(self, *, since: datetime, environment: str, limit: int = 100) -> list[dict]:
        """Find undelivered committed events, including late audit-outbox arrivals.

        Args:
            since: Oldest event within the notification retention interval.
            environment: Deployment environment; excludes other deployments' audit events.
            limit: Maximum pending deliveries, not the number of source records scanned.

        Returns:
            Events without a notification bearing the same stable identifier.

        Notes:
            Separate reads support independent MongoDB servers. No cross-client session
            or cross-database lookup is used. Insert-only destination writes handle races.
        """
        query = {
            "occurred_at": {"$gte": since},
            "source.environment": environment,
            "outcome": "success",
            "$or": [
                {"event_type": "report.saved"},
                {"event_type": "knowledgebase.oncokb_public.refresh.completed"},
                {
                    "event_type": "api.mutation.succeeded",
                    "resource.type": {
                        "$in": [
                            "asp",
                            "aspc",
                            "assay_group",
                            "subpanel",
                            "assay_subpanel",
                            "assay_setup",
                            "genelist",
                        ]
                    },
                },
            ],
        }
        result = []
        cursor = iter(
            self.audit.find(
                query,
                {
                    "occurred_at": 1,
                    "event_type": 1,
                    "resource": 1,
                    "actor.username": 1,
                    "metadata.action": 1,
                    "metadata.sample_oid": 1,
                    "metadata.report_num": 1,
                },
            ).sort("occurred_at", 1)
        )
        while batch := list(islice(cursor, 256)):
            delivered = {
                row["_id"]
                for row in self.notifications.find(
                    {"_id": {"$in": [event["_id"] for event in batch]}}, {"_id": 1}
                )
            }
            for event in batch:
                if event["_id"] not in delivered:
                    result.append(event)
                    if len(result) >= limit:
                        return result
        for release in self.versions.find(
            {
                "published_at": {"$gte": since},
                "status": {"$in": ["active", "retired"]},
            }
        ).sort("published_at", 1):
            identity = ObjectId(
                sha256(
                    f"knowledgebase:{release['_id']}:{release['published_at'].isoformat()}".encode()
                ).hexdigest()[:24]
            )
            if self.notifications.find_one({"_id": identity}, {"_id": 1}):
                continue
            result.append(
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
            if len(result) >= limit:
                break
        return result
