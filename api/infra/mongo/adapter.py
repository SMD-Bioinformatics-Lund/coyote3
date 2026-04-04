"""MongoDB adapter entrypoint for the API."""

from __future__ import annotations

from api.infra.db.mongo import MongoAdapter as _InfraMongoAdapter

MongoAdapter = _InfraMongoAdapter


def create_mongo_adapter() -> MongoAdapter:
    """Create an uninitialized Mongo adapter."""
    return MongoAdapter()
