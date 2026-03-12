"""Service for sample-scoped small variant workflows."""

from __future__ import annotations

from api.services.dna_service import DnaService


class SmallVariantService(DnaService):
    """Canonical service for SNV/indel/MNV workflows."""


__all__ = ["SmallVariantService"]
