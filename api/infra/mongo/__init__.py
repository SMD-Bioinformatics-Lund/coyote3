"""MongoDB runtime support for the API."""

from api.infra.mongo.adapter import MongoAdapter, create_mongo_adapter

__all__ = ["MongoAdapter", "create_mongo_adapter"]
