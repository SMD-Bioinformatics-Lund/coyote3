"""Service for sample-scoped fusion workflows."""

from __future__ import annotations

from api.services.rna.expression_analysis import RnaService


class FusionService(RnaService):
    """Canonical service for fusion workflows."""


__all__ = ["FusionService"]
