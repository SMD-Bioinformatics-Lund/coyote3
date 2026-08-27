"""MongoDB persistence for recipient-scoped application notifications."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from api.infra.mongo.repositories.base import BaseRepository


class NotificationsRepository(BaseRepository):
    """Store broadcasts and user-addressed messages with per-user state."""

    def __init__(self, adapter: Any) -> None:
        super().__init__(adapter)
        self.set_collection(self.adapter.notifications_collection)

    def ensure_indexes(self) -> None:
        collection = self.get_collection()
        collection.create_index([("created_on", -1)], name="created_on_-1", background=True)
        collection.create_index(
            [("audience", 1), ("recipients", 1), ("created_on", -1)],
            name="audience_1_recipients_1_created_on_-1",
            background=True,
        )
        collection.create_index([("expires_on", 1)], name="expires_on_1", expireAfterSeconds=0)

    @staticmethod
    def _visible_query(username: str) -> dict[str, Any]:
        normalized = str(username or "").strip().lower()
        return {
            "$and": [
                {"$or": [{"audience": "all"}, {"recipients": normalized}]},
                {"dismissed_by": {"$ne": normalized}},
            ]
        }

    def create(self, document: dict[str, Any]) -> str:
        result = self.get_collection().insert_one(dict(document))
        return str(result.inserted_id)

    def list_for_user(self, username: str, *, limit: int = 200) -> list[dict[str, Any]]:
        bounded = max(1, min(int(limit or 200), 500))
        return list(
            self.get_collection()
            .find(self._visible_query(username))
            .sort("created_on", -1)
            .limit(bounded)
        )

    def mark_read(self, notification_id: str, username: str) -> bool:
        try:
            object_id = ObjectId(notification_id)
        except Exception:
            return False
        query = {"_id": object_id, **self._visible_query(username)}
        result = self.get_collection().update_one(
            query,
            {
                "$addToSet": {"read_by": str(username).strip().lower()},
                "$set": {"updated_on": datetime.now(timezone.utc)},
            },
        )
        return bool(result.matched_count)

    def mark_all_read(self, username: str) -> int:
        normalized = str(username or "").strip().lower()
        result = self.get_collection().update_many(
            self._visible_query(normalized),
            {
                "$addToSet": {"read_by": normalized},
                "$set": {"updated_on": datetime.now(timezone.utc)},
            },
        )
        return int(result.modified_count)

    def dismiss(self, notification_id: str, username: str) -> bool:
        try:
            object_id = ObjectId(notification_id)
        except Exception:
            return False
        normalized = str(username or "").strip().lower()
        result = self.get_collection().update_one(
            {"_id": object_id, **self._visible_query(normalized)},
            {
                "$addToSet": {"dismissed_by": normalized},
                "$set": {"updated_on": datetime.now(timezone.utc)},
            },
        )
        return bool(result.matched_count)

    def dismiss_all(self, username: str) -> int:
        normalized = str(username or "").strip().lower()
        result = self.get_collection().update_many(
            self._visible_query(normalized),
            {
                "$addToSet": {"dismissed_by": normalized},
                "$set": {"updated_on": datetime.now(timezone.utc)},
            },
        )
        return int(result.modified_count)
