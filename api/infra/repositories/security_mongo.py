"""Mongo-backed repository adapter for API security services."""

from __future__ import annotations

from typing import Any

from api.extensions import store


class MongoSecurityRepository:
    def get_role(self, role_id: str | None) -> dict[str, Any] | None:
        if not role_id:
            return None
        return store.roles_handler.get_role(role_id)

    def get_all_roles(self) -> list[dict[str, Any]]:
        return list(store.roles_handler.get_all_roles() or [])

    def get_all_active_asps(self) -> list[dict[str, Any]]:
        return list(store.asp_handler.get_all_asps(is_active=True) or [])

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        return store.user_handler.user(username)

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        return store.user_handler.user_with_id(str(user_id))

    def get_sample(self, sample_id: str) -> dict[str, Any] | None:
        return store.sample_handler.get_sample(sample_id)

    def get_sample_by_id(self, sample_id: str) -> dict[str, Any] | None:
        return store.sample_handler.get_sample_by_id(sample_id)

    def update_user_last_login(self, user_id: str) -> None:
        store.user_handler.update_user_last_login(user_id)
