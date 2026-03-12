"""Mongo-backed repository for core-layer data access."""

from __future__ import annotations

from bson.objectid import ObjectId
from api.extensions import store


class MongoCoreStoreRepository:
    """Provide mongo core store persistence operations.
    """
    def __init__(self) -> None:
        """Handle __init__.
        """
        self.sample_handler = store.sample_handler
        self.reported_variants_handler = store.reported_variants_handler
        self.annotation_handler = store.annotation_handler

    def new_object_id(self) -> ObjectId:
        """Handle new object id.

        Returns:
            ObjectId: The function result.
        """
        return ObjectId()
