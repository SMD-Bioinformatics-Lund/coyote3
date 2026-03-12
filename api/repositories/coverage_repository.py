"""Canonical coverage repository exports."""

from api.infra.repositories.coverage_mongo import MongoCoverageRepository as CoverageRepository
from api.infra.repositories.coverage_route_mongo import (
    MongoCoverageRouteRepository as CoverageRouteRepository,
)

__all__ = ["CoverageRepository", "CoverageRouteRepository"]
