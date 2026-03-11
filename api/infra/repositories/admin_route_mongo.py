"""Mongo-backed facade for admin route data access.

This is a transitional adapter that lets routes stop calling `store.*` directly
while preserving current behavior.
"""

from __future__ import annotations

from api.extensions import store


class MongoAdminRouteRepository:
    def __getattr__(self, name: str):
        return getattr(store, name)

