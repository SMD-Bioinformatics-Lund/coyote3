"""MongoDB persistence for recipient-scoped application notifications."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from bson import ObjectId
from pymongo import ReturnDocument

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
        """Declare chronological, recipient, visibility-expiry, and email-state indexes."""
        collection = self.get_collection()
        collection.create_index([("created_on", -1)], name="created_on_-1", background=True)
        collection.create_index(
            [("audience", 1), ("recipients", 1), ("created_on", -1)],
            name="audience_1_recipients_1_created_on_-1",
            background=True,
        )
        collection.create_index([("expires_on", 1)], name="expires_on_1")
        collection.create_index([("email_deliveries.state", 1)], name="email_deliveries_state")

    def claim_email(self) -> tuple[dict[str, Any], dict[str, Any]] | None:
        """Lease one pending broadcast email, recovering abandoned attempts.

        Returns:
            Notification and leased recipient entry, or None when no work is ready.

        Notes:
            A single-document atomic update owns the lease. SMTP runs outside MongoDB.
            Abandoned attempts are bounded to three; SMTP cannot guarantee exactly-once delivery.
        """
        now = datetime.now(timezone.utc)
        lease_id = uuid4().hex
        eligible = {
            "$or": [
                {"state": "pending"},
                {"state": "sending", "lease_until": {"$lt": now}},
            ]
        }
        candidate = self.get_collection().find_one(
            {
                "$or": [{"expires_on": None}, {"expires_on": {"$gt": now}}],
                "withdrawn_on": None,
                "email_deliveries": {"$elemMatch": eligible},
            },
            {"email_deliveries": {"$elemMatch": eligible}},
        )
        if candidate is None:
            return None
        previous = candidate["email_deliveries"][0]
        row = self.get_collection().find_one_and_update(
            {
                "_id": candidate["_id"],
                "$or": [{"expires_on": None}, {"expires_on": {"$gt": now}}],
                "withdrawn_on": None,
                "email_deliveries": {
                    "$elemMatch": {
                        "username": previous["username"],
                        "state": previous["state"],
                        "lease_id": previous.get("lease_id"),
                    }
                },
            },
            {
                "$set": {
                    "email_deliveries.$.state": "sending",
                    "email_deliveries.$.lease_id": lease_id,
                    "email_deliveries.$.lease_until": now + timedelta(minutes=2),
                },
                "$inc": {"email_deliveries.$.attempts": 1},
            },
            return_document=ReturnDocument.AFTER,
        )
        if row is None:
            return None
        delivery = next(
            item for item in row["email_deliveries"] if item.get("lease_id") == lease_id
        )
        return row, delivery

    def finish_email(self, notification_id: Any, lease_id: str, *, state: str) -> None:
        """Record a leased recipient's terminal outcome without overwriting another worker.

        Args:
            notification_id: Stored notification identifier.
            lease_id: Token returned by claim_email.
            state: Terminal outcome: sent, failed, skipped, or unknown after abandoned attempts.
        """
        if state not in {"sent", "failed", "skipped", "unknown"}:
            raise ValueError("Invalid email delivery outcome")
        self.get_collection().update_one(
            {
                "_id": notification_id,
                "email_deliveries": {
                    "$elemMatch": {
                        "lease_id": lease_id,
                        "state": "sending",
                    }
                },
            },
            {
                "$set": {
                    "email_deliveries.$.state": state,
                    "email_deliveries.$.finished_on": datetime.now(timezone.utc),
                }
            },
        )

    @staticmethod
    def _visible_query(username: str) -> dict[str, Any]:
        """Select broadcasts or addressed messages not dismissed by a user.

        Args:
            username: Recipient identity, stripped and lowercased; falsey values
                normalize to an empty string.

        Returns:
            MongoDB selector excluding expired and withdrawn messages, and personal dismissals.
        """
        normalized = str(username or "").strip().lower()
        return {
            "$and": [
                {"$or": [{"audience": "all"}, {"recipients": normalized}]},
                {"$or": [{"is_broadcast": True}, {"dismissed_by": {"$ne": normalized}}]},
                {"withdrawn_on": None},
                {
                    "$or": [
                        {"expires_on": None},
                        {"expires_on": {"$gt": datetime.now(timezone.utc)}},
                    ]
                },
            ]
        }

    def get_notification(self, notification_id: str) -> dict[str, Any] | None:
        """Look up a notification for ownership checks, including expired records.

        Args:
            notification_id: Serialized MongoDB ObjectId.

        Returns:
            Stored record, or None for an invalid or unknown identifier. The caller
            must check ownership before exposing content or allowing withdrawal.
        """
        if not ObjectId.is_valid(notification_id):
            return None
        return self.get_collection().find_one({"_id": ObjectId(notification_id)})

    def list_sent(self, username: str, *, limit: int = 200) -> list[dict[str, Any]]:
        """Return the sender's broadcasts, including withdrawn and expired records.

        Args:
            username: Canonical authenticated sender login.
            limit: Maximum rows, clamped to 1 through 500.

        Returns:
            Sender-owned broadcasts ordered newest first.
        """
        return list(
            self.get_collection()
            .find({"is_broadcast": True, "created_by": username})
            .sort("created_on", -1)
            .limit(max(1, min(limit, 500)))
        )

    def withdraw(self, notification_id: str, username: str) -> bool:
        """Atomically withdraw a sender-owned broadcast without deleting its record.

        Args:
            notification_id: Previously validated notification ObjectId string.
            username: Authenticated sender login, matched again in the write selector.

        Returns:
            True for the first successful withdrawal; False for an already withdrawn
            record, a missing record, or an ownership mismatch.
        """
        result = self.get_collection().update_one(
            {
                "_id": ObjectId(notification_id),
                "is_broadcast": True,
                "created_by": username,
                "withdrawn_on": None,
            },
            {"$set": {"withdrawn_on": datetime.now(timezone.utc), "withdrawn_by": username}},
        )
        return bool(result.modified_count)

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
            {"_id": object_id, "is_broadcast": {"$ne": True}, **self._visible_query(normalized)},
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
            {**self._visible_query(normalized), "is_broadcast": {"$ne": True}},
            {
                "$addToSet": {"dismissed_by": normalized},
                "$set": {"updated_on": datetime.now(timezone.utc)},
            },
        )
        return int(result.modified_count)
