"""MongoDB adapter entrypoint for the API."""

from __future__ import annotations

from api.infra.mongo.runtime_adapter import MongoAdapter


def create_mongo_adapter() -> MongoAdapter:
    """Create an uninitialized Mongo adapter."""
    return MongoAdapter()
