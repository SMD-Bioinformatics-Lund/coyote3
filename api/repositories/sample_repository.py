"""Sample repository facade."""

from api.infra.repositories.samples_mongo import MongoSamplesRepository


class SampleRepository(MongoSamplesRepository):
    """Concrete sample repository facade."""


__all__ = ["SampleRepository"]
