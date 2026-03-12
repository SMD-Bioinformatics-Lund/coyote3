"""Canonical internal repository."""

from api.infra.repositories.internal_mongo import MongoInternalRepository as InternalRepository

__all__ = ["InternalRepository"]
