"""Mongo-backed repository for admin route data access."""

from __future__ import annotations

from api.extensions import store


class MongoAdminRouteRepository:
    """Provide mongo admin route persistence operations."""

    def __init__(self) -> None:
        """__init__."""
        self.permissions_handler = store.permissions_handler
        self.roles_handler = store.roles_handler
        self.asp_handler = store.asp_handler
        self.user_handler = store.user_handler
        self.isgl_handler = store.isgl_handler
        self.aspc_handler = store.aspc_handler
        self.sample_handler = store.sample_handler
