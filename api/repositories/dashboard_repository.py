"""Dashboard repository facade."""

from api.infra.repositories.dashboard_mongo import MongoDashboardRepository


class DashboardRepository(MongoDashboardRepository):
    """Concrete dashboard repository facade."""


__all__ = ["DashboardRepository"]
