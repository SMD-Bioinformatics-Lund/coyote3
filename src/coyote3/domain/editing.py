"""Persistence boundary for atomic, expiring document edit leases."""

from datetime import datetime
from typing import Any, Protocol


class EditLeaseRepository(Protocol):
    """Coordinate editor ownership across API workers using shared persistence."""

    def acquire(
        self, key: str, *, owner: str, editor_id: str, now: datetime, expires_at: datetime
    ) -> dict[str, Any] | None:
        """Acquire an absent/expired lease or refresh this same owner and editor."""
        ...

    def renew(
        self, key: str, *, owner: str, editor_id: str, now: datetime, expires_at: datetime
    ) -> dict[str, Any] | None:
        """Extend only a still-live lease owned by this exact editor session."""
        ...

    def read(self, key: str, *, now: datetime) -> dict[str, Any] | None:
        """Return current ownership, treating expired documents as unlocked."""
        ...

    def release(self, key: str, *, owner: str, editor_id: str) -> bool:
        """Remove only the matching owner's editor lease; return whether it was removed."""
        ...
