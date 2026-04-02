"""Service for sample-scoped CNV workflows."""

from __future__ import annotations

from api.services.dna.structural_variants import DnaStructuralService


class CnvService(DnaStructuralService):
    """Canonical service for CNV workflows."""


__all__ = ["CnvService"]
