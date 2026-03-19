"""Mongo repository adapter for internal utility endpoints."""

from __future__ import annotations

from api.extensions import store


class MongoInternalRepository:
    """Provide mongo internal persistence operations."""

    def get_all_roles(self) -> list[dict]:
        """Return all roles.

        Returns:
            list[dict]: The function result.
        """
        return list(store.roles_handler.get_all_roles() or [])

    def is_isgl_adhoc(self, isgl_id: str) -> bool:
        """Return whether isgl adhoc is true.

        Args:
            isgl_id (str): Value for ``isgl_id``.

        Returns:
            bool: The function result.
        """
        return bool(store.isgl_handler.is_isgl_adhoc(isgl_id))

    def get_isgl_display_name(self, isgl_id: str) -> str | None:
        """Return isgl display name.

        Args:
            isgl_id (str): Value for ``isgl_id``.

        Returns:
            str | None: The function result.
        """
        return store.isgl_handler.get_isgl_display_name(isgl_id)
