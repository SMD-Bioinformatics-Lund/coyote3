"""Canonical admin repository exports."""

from api.infra.repositories.admin_route_mongo import MongoAdminRouteRepository as AdminRepository
from api.infra.repositories.admin_sample_mongo import (
    MongoAdminSampleDeletionRepository as AdminSampleDeletionRepository,
)

__all__ = ["AdminRepository", "AdminSampleDeletionRepository"]
