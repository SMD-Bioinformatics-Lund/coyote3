"""Canonical public catalog repository."""

from api.infra.repositories.public_catalog_mongo import (
    MongoPublicCatalogRepository as PublicCatalogRepository,
)

__all__ = ["PublicCatalogRepository"]
