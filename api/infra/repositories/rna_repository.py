"""RNA repository adapters."""

from __future__ import annotations

from api.extensions import store
from api.infra.repositories.rna_workflow_mongo import RnaWorkflowRepository


class RnaRouteRepository:
    """Repository for RNA route handlers with dynamic handler resolution."""

    @property
    def asp_handler(self):
        """Asp handler.

        Returns:
            The function result.
        """
        return store.asp_handler

    @property
    def isgl_handler(self):
        """Isgl handler.

        Returns:
            The function result.
        """
        return store.isgl_handler

    @property
    def sample_handler(self):
        """Sample handler.

        Returns:
            The function result.
        """
        return store.sample_handler

    @property
    def fusion_handler(self):
        """Fusion handler.

        Returns:
            The function result.
        """
        return store.fusion_handler


__all__ = ["RnaRouteRepository", "RnaWorkflowRepository"]
