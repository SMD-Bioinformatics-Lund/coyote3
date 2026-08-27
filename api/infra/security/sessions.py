"""Mongo-backed opaque API session repository."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from api.config.constants import DEFAULT_AUTH_PROVIDER
from api.security.tokens import issue_opaque_token, token_hash


@dataclass(frozen=True, slots=True)
class ApiSession:
    """Resolved API session with the raw token used by the client."""

    token: str
    csrf_token: str
    user: Any
    provider: str


class MongoApiSessionRepository:
    """Persist API sessions as hashed opaque tokens in MongoDB."""

    def __init__(self, collection: Any, *, user_loader: Any, ttl_seconds: int) -> None:
        self.collection = collection
        self.user_loader = user_loader
        self.ttl_seconds = int(ttl_seconds)

    def create(self, user: Any, *, provider: str = DEFAULT_AUTH_PROVIDER) -> ApiSession:
        token = issue_opaque_token(48)
        csrf_token = issue_opaque_token(32)
        now = datetime.now(timezone.utc)
        self.collection.insert_one(
            {
                "_id": token_hash(token),
                "user_id": user.username,
                "provider": provider,
                "csrf_token": csrf_token,
                "created_at": now,
                "last_seen_at": now,
                "expires_at": now + timedelta(seconds=self.ttl_seconds),
            }
        )
        return ApiSession(token=token, csrf_token=csrf_token, user=user, provider=provider)

    def get(self, token: str) -> ApiSession | None:
        now = datetime.now(timezone.utc)
        document = self.collection.find_one({"_id": token_hash(token), "expires_at": {"$gt": now}})
        if not isinstance(document, dict):
            return None
        user = self.user_loader(str(document.get("user_id") or ""))
        if user is None:
            return None
        self.collection.update_one(
            {"_id": document["_id"]},
            {"$set": {"last_seen_at": now}},
        )
        return ApiSession(
            token=token,
            csrf_token=str(document.get("csrf_token") or ""),
            user=user,
            provider=str(document.get("provider") or DEFAULT_AUTH_PROVIDER),
        )

    def delete(self, token: str) -> None:
        self.collection.delete_one({"_id": token_hash(token)})
