"""User application service."""

from __future__ import annotations

from api.extensions import store
from api.security.ports import SecurityRepository


class UserService:
    """Thin service layer around user lookup operations."""

    def __init__(self, repository: SecurityRepository | None = None) -> None:
        """Build the service with a user lookup repository."""
        self.repository = repository or store.get_security_repository()

    def get_user_by_id(self, user_id: str):
        """Return user by id.

        Args:
            user_id (str): Value for ``user_id``.

        Returns:
            The function result.
        """
        return self.repository.get_user_by_id(user_id)
