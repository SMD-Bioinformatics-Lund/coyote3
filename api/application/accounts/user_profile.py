"""User application service."""

from __future__ import annotations

from typing import Any


class UserService:
    """Thin service layer around user lookup operations."""

    @classmethod
    def from_store(cls, store: Any) -> "UserService":
        """Build the service from the runtime store."""
        return cls(user_repository=store.user_repository)

    def __init__(self, *, user_repository: Any) -> None:
        """Create the service with an injected user repository."""
        self.user_repository = user_repository

    def get_user_by_id(self, user_id: str):
        """Return a user document by identifier."""
        return self.user_repository.user_with_id(user_id)
