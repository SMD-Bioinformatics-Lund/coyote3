"""Service for sample-scoped biomarker workflows."""

from __future__ import annotations

from typing import Any

from api.http import api_error


class BiomarkerService:
    """Provide biomarker workflows."""

    @classmethod
    def from_store(cls, store: Any) -> "BiomarkerService":
        """Build the service from the shared store."""
        return cls(biomarker_handler=store.biomarker_handler)

    def __init__(self, *, biomarker_handler: Any) -> None:
        """Create the service with an injected biomarker handler."""
        self.biomarker_handler = biomarker_handler

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
            self.biomarker_handler.get_sample_biomarkers(sample_id=str(sample["_id"]))
        )
        return {"sample": sample, "meta": {"count": len(biomarkers)}, "biomarkers": biomarkers}


__all__ = ["BiomarkerService"]
