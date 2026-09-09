"""MongoDB persistence for recipient-scoped application notifications."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from api.infra.mongo.repositories.base import BaseRepository


class NotificationsRepository(BaseRepository):
    """Store broadcasts and user-addressed messages with per-user state."""

    def __init__(self, adapter: Any) -> None:
        """Bind the application notification collection.

        Args:
            adapter: Mongo adapter exposing ``notifications_collection``.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.notifications_collection)

    def ensure_indexes(self) -> None:
        """Create chronological, audience/recipient, and expiration TTL indexes."""
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
        """Select broadcasts or addressed messages not dismissed by a user.

        Args:
            username: Recipient identity, stripped and lowercased; falsey values
                normalize to an empty string.

        Returns:
            MongoDB selector for audience and dismissal state, without an expiry filter.
        """
        normalized = str(username or "").strip().lower()
        return {
            "$and": [
                {"$or": [{"audience": "all"}, {"recipients": normalized}]},
                {"dismissed_by": {"$ne": normalized}},
            ]
        }

    def create(self, document: dict[str, Any]) -> str:
        """Insert a shallow copy of a notification document.

        Args:
            document: Notification fields prepared by the caller.

        Returns:
            Serialized inserted document ID.
        """
        result = self.get_collection().insert_one(dict(document))
        return str(result.inserted_id)

    def list_for_user(self, username: str, *, limit: int = 200) -> list[dict[str, Any]]:
        """List a user's undismissed notifications with newest messages first.

        Args:
            username: Recipient identity, stripped and lowercased for matching.
            limit: Maximum results, clamped to 1 through 500; falsey values use 200.

        Returns:
            Broadcasts and addressed messages not dismissed by this user.
        """
        bounded = max(1, min(int(limit or 200), 500))
        return list(
            self.get_collection()
            .find(self._visible_query(username))
            .sort("created_on", -1)
            .limit(bounded)
        )

    def mark_read(self, notification_id: str, username: str) -> bool:
        """Add a user to a visible notification's read set and update its timestamp.

        Args:
            notification_id: Serialized notification ObjectId.
            username: Reader identity, stripped and lowercased.

        Returns:
            Whether a visible document matched, including an already-read message;
            ``False`` also covers invalid IDs.
        """
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
        """Mark all visible notifications read by a user in one transaction.

        Args:
            username: Reader identity, stripped and lowercased.

        Returns:
            Modified document count, including changes to update timestamps.
        """
        normalized = str(username or "").strip().lower()
        result = self.update_many_atomic(
            self._visible_query(normalized),
            {
                "$addToSet": {"read_by": normalized},
                "$set": {"updated_on": datetime.now(timezone.utc)},
            },
        )
        return int(result.modified_count)

    def dismiss(self, notification_id: str, username: str) -> bool:
        """Add a user to a visible notification's dismissal set.

        Args:
            notification_id: Serialized notification ObjectId.
            username: Recipient identity, stripped and lowercased.

        Returns:
            Whether a visible document matched; ``False`` for invalid IDs, absent
            messages, or messages already dismissed by this user.
        """
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
        """Dismiss all currently visible messages for a user in one transaction.

        Args:
            username: Recipient identity, stripped and lowercased.

        Returns:
            Number of notification documents modified.
        """
        normalized = str(username or "").strip().lower()
        result = self.update_many_atomic(
            self._visible_query(normalized),
            {
                "$addToSet": {"dismissed_by": normalized},
                "$set": {"updated_on": datetime.now(timezone.utc)},
            },
        )
        return int(result.modified_count)
