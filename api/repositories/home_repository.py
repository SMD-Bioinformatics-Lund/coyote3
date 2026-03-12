"""Home repository facade."""

from api.infra.repositories.home_mongo import MongoHomeRepository


class HomeRepository(MongoHomeRepository):
    """Concrete home repository facade."""


__all__ = ["HomeRepository"]
