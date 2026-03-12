"""Ports for security/auth data access."""

from __future__ import annotations

from typing import Any, Protocol


class SecurityRepository(Protocol):
    """Define the persistence operations required by security workflows."""

    def get_role(self, role_id: str | None) -> dict[str, Any] | None:
        """Return role.

        Args:
            role_id (str | None): Value for ``role_id``.

        Returns:
            dict[str, Any] | None: The function result.
        """
        ...

    def get_all_roles(self) -> list[dict[str, Any]]:
        """Return all roles.

        Returns:
            list[dict[str, Any]]: The function result.
        """
        ...

    def get_all_active_asps(self) -> list[dict[str, Any]]:
        """Return all active asps.

        Returns:
            list[dict[str, Any]]: The function result.
        """
        ...

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        """Return user by username.

        Args:
            username (str): Value for ``username``.

        Returns:
            dict[str, Any] | None: The function result.
        """
        ...

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        """Return user by id.

        Args:
            user_id (str): Value for ``user_id``.

        Returns:
            dict[str, Any] | None: The function result.
        """
        ...

    def get_sample(self, sample_id: str) -> dict[str, Any] | None:
        """Return sample.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            dict[str, Any] | None: The function result.
        """
        ...

    def get_sample_by_id(self, sample_id: str) -> dict[str, Any] | None:
        """Return sample by id.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            dict[str, Any] | None: The function result.
        """
        ...

    def update_user_last_login(self, user_id: str) -> None:
        """Update user last login.

        Args:
            user_id (str): Value for ``user_id``.

        Returns:
            None.
        """
        ...
