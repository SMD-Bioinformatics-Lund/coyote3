"""Canonical dashboard repository."""

from api.infra.repositories.dashboard_mongo import MongoDashboardRepository as DashboardRepository

__all__ = ["DashboardRepository"]
