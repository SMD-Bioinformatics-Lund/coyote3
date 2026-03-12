"""MongoDB runtime support for the API."""

from api.db.mongo.main import MongoAdapter, create_mongo_adapter

__all__ = ["MongoAdapter", "create_mongo_adapter"]
