"""Internal repository facade."""

from api.infra.repositories.internal_mongo import MongoInternalRepository


class InternalRepository(MongoInternalRepository):
    """Concrete internal repository facade."""


__all__ = ["InternalRepository"]
