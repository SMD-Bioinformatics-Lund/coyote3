"""Mongo repository adapter for internal utility endpoints."""

from __future__ import annotations

from api.extensions import store


class MongoInternalRepository:
    def get_all_roles(self) -> list[dict]:
        return list(store.roles_handler.get_all_roles() or [])

    def is_isgl_adhoc(self, isgl_id: str) -> bool:
        return bool(store.isgl_handler.is_isgl_adhoc(isgl_id))

    def get_isgl_display_name(self, isgl_id: str) -> str | None:
        return store.isgl_handler.get_isgl_display_name(isgl_id)
