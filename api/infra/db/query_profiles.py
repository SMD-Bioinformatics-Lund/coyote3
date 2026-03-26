"""Mongo handler for query-profile option lookups."""

from __future__ import annotations

from typing import Any

from api.infra.db.base import BaseHandler


class QueryProfilesHandler(BaseHandler):
    """Lookup helpers for query profile documents."""

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.query_profiles_collection)

    def ensure_indexes(self) -> None:
        col = self.get_collection()
        col.create_index(
            [("query_profile_id", 1)],
            name="query_profile_id_1",
            unique=True,
            background=True,
            partialFilterExpression={"query_profile_id": {"$exists": True, "$type": "string"}},
        )
        col.create_index(
            [
                ("is_active", 1),
                ("resource_type", 1),
                ("assay_groups", 1),
                ("assays", 1),
                ("environment", 1),
            ],
            name="is_active_resource_scope_env_1",
            background=True,
        )

    def list_query_profiles(self, *, is_active: bool | None = None) -> list[dict[str, Any]]:
        query: dict[str, Any] = {}
        if is_active is not None:
            query["is_active"] = is_active
        return list(self.get_collection().find(query))
