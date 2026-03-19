"""Repository port for internal utility endpoints."""

from __future__ import annotations

from typing import Protocol


class InternalRepository(Protocol):
    """Define the persistence operations required by internal support routes."""

    def get_all_roles(self) -> list[dict]:
        """Return all roles.

        Returns:
            list[dict]: The function result.
        """
        ...

    def is_isgl_adhoc(self, isgl_id: str) -> bool:
        """Return whether isgl adhoc is true.

        Args:
            isgl_id (str): Value for ``isgl_id``.

        Returns:
            bool: The function result.
        """
        ...

    def get_isgl_display_name(self, isgl_id: str) -> str | None:
        """Return isgl display name.

        Args:
            isgl_id (str): Value for ``isgl_id``.

        Returns:
            str | None: The function result.
        """
        ...
