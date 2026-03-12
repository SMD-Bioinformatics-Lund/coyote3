"""Common repository facade."""

from api.infra.repositories.common_mongo import MongoCommonRepository


class CommonRepository(MongoCommonRepository):
    """Concrete common repository facade."""


__all__ = ["CommonRepository"]
