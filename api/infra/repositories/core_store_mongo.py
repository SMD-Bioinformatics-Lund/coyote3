"""Mongo-backed shared facade for core-layer data access.

Transitional adapter used to remove direct `store.*` references from core
modules while preserving existing behavior.
"""

from __future__ import annotations

from bson.objectid import ObjectId
from api.extensions import store


class MongoCoreStoreRepository:
    def __getattr__(self, name: str):
        return getattr(store, name)

    def new_object_id(self) -> ObjectId:
        return ObjectId()
