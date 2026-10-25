"""MongoDB compare-and-set ownership for document editing sessions."""

from datetime import datetime
from typing import Any

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from api.config.operational_collections import OPERATIONAL_COLLECTIONS
from api.infra.mongo.repositories.base import BaseRepository


class MongoEditLeaseRepository(BaseRepository):
    """Use the unique document key to resolve competing acquisitions atomically."""

    def __init__(self, adapter: Any) -> None:
        """Bind lease persistence to the primary application database.

        Args:
            adapter: Configured MongoDB adapter with the primary database handle.
        """
        super().__init__(adapter)
        self.set_collection(adapter.coyote_db[OPERATIONAL_COLLECTIONS.edit_leases])

    def ensure_indexes(self) -> None:
        """Schedule expired lease cleanup; correctness never depends on TTL timing."""
        self.get_collection().create_index(
            [("expires_at", 1)], expireAfterSeconds=0, name="edit_lease_expiry"
        )

    def acquire(
        self, key: str, *, owner: str, editor_id: str, now: datetime, expires_at: datetime
    ) -> dict[str, Any] | None:
        """Claim a vacant/expired key or refresh the same editor's existing ownership.

        Args:
            key: Canonical resource identity shared by every write path.
            owner: Authenticated username, never supplied by the request body.
            editor_id: Unique editing-session identifier, separate from login identity.
            now: Current UTC time used to reject leases still owned by another editor.
            expires_at: New UTC expiry assigned by the application service.

        Returns:
            Acquired lease, or None when another editor holds the key.
        """
        try:
            return self.get_collection().find_one_and_update(
                {
                    "_id": key,
                    "$or": [
                        {"expires_at": {"$lte": now}},
                        {"owner": owner, "editor_id": editor_id},
                    ],
                },
                {"$set": {"owner": owner, "editor_id": editor_id, "expires_at": expires_at}},
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError:
            return None

    def renew(
        self, key: str, *, owner: str, editor_id: str, now: datetime, expires_at: datetime
    ) -> dict[str, Any] | None:
        """Renew an unexpired matching lease without resurrecting lost ownership.

        Args:
            key: Canonical document key.
            owner: Authenticated username.
            editor_id: Editing-session identifier from acquisition.
            now: Current UTC time; leases at or before it cannot be renewed.
            expires_at: New application-assigned UTC expiry.

        Returns:
            Renewed lease, or None when it expired, was released or belongs to another editor.
        """
        return self.get_collection().find_one_and_update(
            {"_id": key, "owner": owner, "editor_id": editor_id, "expires_at": {"$gt": now}},
            {"$set": {"expires_at": expires_at}},
            return_document=ReturnDocument.AFTER,
        )

    def read(self, key: str, *, now: datetime) -> dict[str, Any] | None:
        """Read a live lease without relying on TTL cleanup.

        Args:
            key: Canonical resource key.
            now: Current UTC time; expiry at or before it is treated as unlocked.

        Returns:
            Current ownership or None when unlocked.
        """
        return self.get_collection().find_one({"_id": key, "expires_at": {"$gt": now}})

    def release(self, key: str, *, owner: str, editor_id: str) -> bool:
        """Release an exact editor session, preserving any successor lease.

        Args:
            key: Canonical resource key.
            owner: Verified username.
            editor_id: Unique session identifier assigned when opening the form.

        Returns:
            Whether this call removed the matching lease.
        """
        result = self.get_collection().delete_one(
            {"_id": key, "owner": owner, "editor_id": editor_id}
        )
        return result.deleted_count == 1
