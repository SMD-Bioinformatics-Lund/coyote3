"""Service for sample-scoped biomarker workflows."""

from __future__ import annotations

from typing import Any

from api.domain.common.errors import api_error


class BiomarkerService:
    """Provide biomarker workflows."""

    @classmethod
    def from_store(cls, store: Any) -> "BiomarkerService":
        """Build the service from the runtime store."""
        return cls(biomarker_repository=store.biomarker_repository)

    def __init__(self, *, biomarker_repository: Any) -> None:
        """Create the service with an injected biomarker repository."""
        self.biomarker_repository = biomarker_repository

    def list_payload(self, *, sample: dict) -> dict:
        """Return biomarker data for a sample.

        Args:
            sample: Sample payload used for biomarker lookup.

        Returns:
            dict: Biomarker payload with sample metadata.
        """
        if not sample:
            raise api_error(404, "Sample not found")
        biomarkers = list(
            self.biomarker_repository.get_sample_biomarkers(sample_id=str(sample["_id"]))
        )
        return {"sample": sample, "meta": {"count": len(biomarkers)}, "biomarkers": biomarkers}


__all__ = ["BiomarkerService"]
