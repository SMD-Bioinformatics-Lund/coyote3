"""Coverage repository facades."""

from api.infra.repositories.coverage_mongo import MongoCoverageRepository
from api.infra.repositories.coverage_route_mongo import MongoCoverageRouteRepository


class CoverageRepository(MongoCoverageRepository):
    """Concrete coverage-processing repository facade."""


class CoverageRouteRepository(MongoCoverageRouteRepository):
    """Concrete route-facing coverage repository facade."""


__all__ = ["CoverageRepository", "CoverageRouteRepository"]
