"""Service for sample-scoped fusion workflows."""

from __future__ import annotations

from api.services.rna_service import RnaService


class FusionService(RnaService):
    """Canonical service for fusion workflows."""


__all__ = ["FusionService"]
