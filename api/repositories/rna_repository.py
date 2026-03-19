"""RNA repository facades."""

from __future__ import annotations

from api.extensions import store
from api.infra.repositories.rna_workflow_mongo import MongoRNAWorkflowRepository


class RnaRouteRepository:
    """Repository facade for RNA route handlers with dynamic handler resolution."""

    @property
    def schema_handler(self):
        """Schema handler.

        Returns:
            The function result.
        """
        return store.schema_handler

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


class RnaWorkflowRepository(MongoRNAWorkflowRepository):
    """Workflow repository facade for RNA service orchestration."""


__all__ = ["RnaRouteRepository", "RnaWorkflowRepository"]
