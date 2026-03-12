"""User application service."""

from __future__ import annotations

from api.repositories.user_repository import UserRepository


class UserService:
    """Thin service layer around user lookup operations."""

    def __init__(self, repository: UserRepository | None = None) -> None:
        """Handle __init__.

        Args:
                repository: Repository. Optional argument.
        """
        self.repository = repository or UserRepository()

    def get_user_by_id(self, user_id: str):
        """Return user by id.

        Args:
            user_id (str): Value for ``user_id``.

        Returns:
            The function result.
        """
        return self.repository.get_user_by_id(user_id)
