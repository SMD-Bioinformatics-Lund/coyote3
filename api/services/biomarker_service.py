"""Service for sample-scoped biomarker workflows."""

from __future__ import annotations

from api.http import api_error
from api.repositories.dna_repository import DnaRouteRepository


class BiomarkerService:
    """Provide biomarker workflows."""

    def __init__(self, repository: DnaRouteRepository | None = None) -> None:
        """Handle __init__.

        Args:
                repository: Repository. Optional argument.
        """
        self.repository = repository or DnaRouteRepository()

    def list_payload(self, *, sample: dict) -> dict:
        """List payload.

        Args:
            sample (dict): Value for ``sample``.

        Returns:
            dict: The function result.
        """
        if not sample:
            raise api_error(404, "Sample not found")
        biomarkers = list(
            self.repository.biomarker_handler.get_sample_biomarkers(sample_id=str(sample["_id"]))
        )
        return {"sample": sample, "meta": {"count": len(biomarkers)}, "biomarkers": biomarkers}


__all__ = ["BiomarkerService"]
