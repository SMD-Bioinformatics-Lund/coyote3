# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Mongo-backed opaque API session repository."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from coyote.application.accounts.tokens import issue_opaque_token, token_hash
from coyote.config.constants import DEFAULT_AUTH_PROVIDER
from coyote.contracts.auth import SessionActivitySummary

from coyote_mongo.config.settings import AuditContext
from coyote_mongo.repositories.mutations import write_with_audit


@dataclass(frozen=True, slots=True)
class ApiSession:
    """Resolved API session with the raw token used by the client."""

    token: str
    csrf_token: str
    user: Any
    provider: str


class MongoApiSessionRepository:
    """Persist API sessions as hashed opaque tokens in MongoDB."""

    def __init__(
        self, collection: Any, *, user_loader: Any, ttl_seconds: int, context: AuditContext
    ) -> None:
        """Bind session persistence and user resolution.

        Args:
            collection: MongoDB collection for hashed session tokens.
            user_loader: Callable resolving a username to a user or ``None``.
            ttl_seconds: Session lifetime in seconds from creation.
            context: Owning deployment's transactional audit identity.
        """
        self.collection = collection
        self.user_loader = user_loader
        self.ttl_seconds = int(ttl_seconds)
        self.audit_context = context

    def create(self, user: Any, *, provider: str = DEFAULT_AUTH_PROVIDER) -> ApiSession:
        """Issue opaque session and CSRF tokens and persist the session hash.

        Args:
            user: User with a username and optional credential version.
            provider: Authentication provider recorded with the session.

        Returns:
            Session containing the raw client token, CSRF token, and supplied user.
        """
        token = issue_opaque_token(48)
        csrf_token = issue_opaque_token(32)
        now = datetime.now(timezone.utc)
        write_with_audit(
            self.collection,
            "insert_one",
            {
                "_id": token_hash(token),
                "user_id": user.username,
                "provider": provider,
                "credential_version": getattr(user, "credential_version", None),
                "csrf_token": csrf_token,
                "created_at": now,
                "last_seen_at": now,
                "expires_at": now + timedelta(seconds=self.ttl_seconds),
            },
            context=self.audit_context,
            record_ids=False,
            actor=user.username,
        )
        return ApiSession(token=token, csrf_token=csrf_token, user=user, provider=provider)

    def get(self, token: str) -> ApiSession | None:
        """Resolve an unexpired session against the user's credential version.

        Args:
            token: Raw client session token; only its hash is queried.

        Returns:
            Resolved session, or ``None`` for a missing or expired session,
            unresolved user, or changed credential version.

        Notes:
            Deletes sessions with mismatched credential versions. Successful reads
            update ``last_seen_at`` but do not extend expiration.
        """
        now = datetime.now(timezone.utc)
        document = self.collection.find_one({"_id": token_hash(token), "expires_at": {"$gt": now}})
        if not isinstance(document, dict):
            return None
        user = self.user_loader(str(document.get("user_id") or ""))
        if user is None:
            return None
        if document.get("credential_version") != getattr(user, "credential_version", None):
            self.delete(token)
            return None
        write_with_audit(
            self.collection,
            "update_one",
            {"_id": document["_id"]},
            {"$set": {"last_seen_at": now}},
            context=self.audit_context,
            record_ids=False,
            actor=user.username,
        )
        return ApiSession(
            token=token,
            csrf_token=str(document.get("csrf_token") or ""),
            user=user,
            provider=str(document.get("provider") or DEFAULT_AUTH_PROVIDER),
        )

    def delete(self, token: str) -> None:
        """Delete a session by its hashed client token.

        Args:
            token: Raw client session token; a missing session is a no-op.
        """
        write_with_audit(
            self.collection,
            "delete_one",
            {"_id": token_hash(token)},
            context=self.audit_context,
            record_ids=False,
        )

    def activity_summary(self, *, recent_activity_seconds: int) -> SessionActivitySummary:
        """Count valid logins without retrieving tokens or refreshing activity.

        Args:
            recent_activity_seconds: Positive lookback window for authenticated requests.

        Returns:
            Session and unique-user counts across this repository's identity store.
            Expiration is checked explicitly, independently of MongoDB TTL cleanup.

        Raises:
            ValueError: The requested activity window is not positive.
        """
        if recent_activity_seconds <= 0:
            raise ValueError("The activity window must be positive")
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=recent_activity_seconds)
        groups = self.collection.aggregate(
            [
                {"$match": {"expires_at": {"$gt": now}}},
                {
                    "$group": {
                        "_id": {"user_id": "$user_id", "credential_version": "$credential_version"},
                        "sessions": {"$sum": 1},
                        "last_seen_at": {"$max": "$last_seen_at"},
                    }
                },
            ]
        )
        users: dict[str, Any] = {}
        signed_in: set[str] = set()
        recently_active: set[str] = set()
        session_count = 0
        for group in groups:
            identity = group["_id"]
            username = identity.get("user_id")
            if not isinstance(username, str) or not username:
                continue
            if username not in users:
                users[username] = self.user_loader(username)
            user = users[username]
            if user is None or identity.get("credential_version") != getattr(
                user, "credential_version", None
            ):
                continue
            signed_in.add(username)
            session_count += group["sessions"]
            last_seen = group.get("last_seen_at")
            if isinstance(last_seen, datetime):
                # PyMongo can decode UTC timestamps without tzinfo.
                if last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=timezone.utc)
                if cutoff <= last_seen <= now:
                    recently_active.add(username)
        return SessionActivitySummary(
            signed_in_users=len(signed_in),
            active_sessions=session_count,
            recently_active_users=len(recently_active),
            recent_activity_seconds=recent_activity_seconds,
            observed_at=now,
        )
