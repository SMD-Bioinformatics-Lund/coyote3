"""Dashboard metrics snapshot repository."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pymongo
from pymongo.errors import OperationFailure

from api.infra.mongo.repositories.base import BaseRepository


class DashboardMetricsRepository(BaseRepository):
    """Manage persisted dashboard metric snapshots."""

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.coyote_db["dashboard_metrics"])

    def ensure_indexes(self) -> None:
        """Create dashboard metrics indexes."""
        ttl_seconds = int(
            self.app.config.get("DASHBOARD_SUMMARY_SNAPSHOT_TTL_SECONDS", 604800) or 0
        )
        if ttl_seconds <= 0:
            self.app.logger.info(
                "Dashboard snapshot TTL disabled (DASHBOARD_SUMMARY_SNAPSHOT_TTL_SECONDS=%s).",
                ttl_seconds,
            )
            return

        try:
            self.get_collection().create_index(
                [("updated_at", pymongo.ASCENDING)],
                name="updated_at_ttl_1",
                expireAfterSeconds=ttl_seconds,
                background=True,
            )
        except OperationFailure as exc:
            code = getattr(exc, "code", None)
            if code == 85:
                self.app.logger.warning(
                    "Skipping dashboard_metrics TTL index conflict: %s",
                    exc,
                )
                return
            raise

    def get_summary_snapshot(self, *, scope_key: str) -> dict | None:
        """Return a persisted dashboard summary snapshot document."""
        return self.get_collection().find_one(
            {"_id": f"dashboard_summary_v2:{scope_key}"},
            {"payload": 1, "updated_at": 1},
        )

    def upsert_summary_snapshot(self, *, scope_key: str, payload: dict[str, Any]) -> None:
        """Persist a dashboard summary snapshot."""
        self.get_collection().update_one(
            {"_id": f"dashboard_summary_v2:{scope_key}"},
            {
                "$set": {
                    "payload": dict(payload),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
