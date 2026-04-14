"""User application service."""

from __future__ import annotations

from typing import Any


class UserService:
    """Thin service layer around user lookup operations."""

    @classmethod
    def from_store(cls, store: Any) -> "UserService":
        """Build the service from the shared store."""
        return cls(user_handler=store.user_handler)

    def __init__(self, *, user_handler: Any) -> None:
        """Create the service with an injected user handler."""
        self.user_handler = user_handler

    def get_user_by_id(self, user_id: str):
        """Return a user document by identifier."""
        return self.user_handler.user_with_id(user_id)
