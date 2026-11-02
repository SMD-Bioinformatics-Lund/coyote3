"""Persistence boundary for managed automation credentials."""

from datetime import datetime
from typing import Any, Protocol


class ServiceTokenRepository(Protocol):
    """Store only credential digests and retain revocation history."""

    def create(self, document: dict[str, Any]) -> None:
        """Persist server-assigned metadata and its credential hash."""
        ...

    def list_metadata(
        self, *, owner: str | None = None, kind: str | None = None
    ) -> list[dict[str, Any]]:
        """Return up to 500 recent records, omitting credential hashes."""
        ...

    def get_metadata(self, token_id: str) -> dict[str, Any] | None:
        """Read nonsecret identity fields for ownership checks without touching usage dates."""
        ...

    def resolve_id(self, token_id: str, *, audience: str, now: datetime) -> dict[str, Any] | None:
        """Resolve a worker's stored public reference against current credential state."""
        ...

    def resolve(self, digest: str, *, audience: str, now: datetime) -> dict[str, Any] | None:
        """Atomically touch and return an unrevoked, unexpired credential in its audience."""
        ...

    def revoke(self, token_id: str, *, actor: str, now: datetime) -> dict[str, Any] | None:
        """Revoke once and return public metadata, or None for an unknown identifier."""
        ...
