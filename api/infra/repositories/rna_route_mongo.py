"""Mongo-backed repository for RNA route data access."""

from __future__ import annotations

from api.extensions import store


class MongoRNARouteRepository:
    """Provide mongo rna route persistence operations.
    """
    def __init__(self) -> None:
        """Handle __init__.
        """
        self.schema_handler = store.schema_handler
        self.asp_handler = store.asp_handler
        self.isgl_handler = store.isgl_handler
        self.sample_handler = store.sample_handler
        self.fusion_handler = store.fusion_handler
