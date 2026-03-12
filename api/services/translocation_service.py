"""Service for sample-scoped translocation workflows."""

from __future__ import annotations

from api.services.dna_structural_service import DnaStructuralService


class TranslocationService(DnaStructuralService):
    """Canonical service for translocation workflows."""


__all__ = ["TranslocationService"]
