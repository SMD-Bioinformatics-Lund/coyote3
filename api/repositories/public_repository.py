"""Public-facing repository facade."""

from api.infra.repositories.public_catalog_mongo import MongoPublicCatalogRepository


class PublicCatalogRepository(MongoPublicCatalogRepository):
    """Concrete public catalog repository facade."""


__all__ = ["PublicCatalogRepository"]
