"""Identity-database storage for individually revocable service credentials."""

from datetime import datetime
from typing import Any

from pymongo import ReturnDocument


class MongoServiceTokenRepository:
    """Keep credential hashes private and revocation checks independent of TTL cleanup."""

    def __init__(self, collection: Any) -> None:
        """Bind identity storage with UTC-aware dates for unambiguous HTTP expiry timestamps."""
        self.collection = collection.with_options(
            codec_options=collection.codec_options.with_options(tz_aware=True)
        )

    def create(self, document: dict[str, Any]) -> None:
        """Store the server-generated record without retaining any raw secret."""
        self.collection.insert_one(document)

    def list_metadata(
        self, *, owner: str | None = None, kind: str | None = None
    ) -> list[dict[str, Any]]:
        """Return the latest 500 records with no credential digest."""
        query = {}
        if owner is not None:
            query["owner"] = owner
        if kind is not None:
            query["kind"] = kind
        return list(
            self.collection.find(query, {"_id": 0, "token_hash": 0})
            .sort("created_at", -1)
            .limit(500)
        )

    def get_metadata(self, token_id: str) -> dict[str, Any] | None:
        """Return nonsecret metadata for a public identifier, or None when absent."""
        return self.collection.find_one({"token_id": token_id}, {"_id": 0, "token_hash": 0})

    def resolve_id(self, token_id: str, *, audience: str, now: datetime) -> dict[str, Any] | None:
        """Recheck a queued job's credential without persisting or reconstructing its secret."""
        return self.collection.find_one(
            {
                "token_id": token_id,
                "audience": audience,
                "revoked_at": None,
                "expires_at": {"$gt": now},
            },
            {"_id": 0, "token_hash": 0},
        )

    def resolve(self, digest: str, *, audience: str, now: datetime) -> dict[str, Any] | None:
        """Touch a currently valid credential atomically; revoked or expired records fail closed."""
        return self.collection.find_one_and_update(
            {
                "token_hash": digest,
                "audience": audience,
                "revoked_at": None,
                "expires_at": {"$gt": now},
            },
            {"$set": {"last_used_at": now}},
            projection={"_id": 0, "token_hash": 0},
            return_document=ReturnDocument.AFTER,
        )

    def revoke(self, token_id: str, *, actor: str, now: datetime) -> dict[str, Any] | None:
        """Preserve the first revocation identity and return metadata for idempotent retries."""
        self.collection.update_one(
            {"token_id": token_id, "revoked_at": None},
            {"$set": {"revoked_at": now, "revoked_by": actor}},
        )
        return self.collection.find_one({"token_id": token_id}, {"_id": 0, "token_hash": 0})
