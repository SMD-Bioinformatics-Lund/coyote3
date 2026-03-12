"""Service for sample-scoped biomarker workflows."""

from __future__ import annotations

from api.http import api_error
from api.repositories.dna_repository import DnaRouteRepository


class BiomarkerService:
    def __init__(self, repository: DnaRouteRepository | None = None) -> None:
        self.repository = repository or DnaRouteRepository()

    def list_payload(self, *, sample: dict) -> dict:
        if not sample:
            raise api_error(404, "Sample not found")
        biomarkers = list(self.repository.biomarker_handler.get_sample_biomarkers(sample_id=str(sample["_id"])))
        return {"sample": sample, "meta": {"count": len(biomarkers)}, "biomarkers": biomarkers}


__all__ = ["BiomarkerService"]
