"""Admin sample deletion service utilities."""

from __future__ import annotations

from api.core.admin.ports import AdminSampleDeletionRepository


class SampleDeletionService:
    """Provide sample deletion workflows.
    """
    _repository: AdminSampleDeletionRepository | None = None

    @classmethod
    def set_repository(cls, repository: AdminSampleDeletionRepository) -> None:
        """Set repository.

        Args:
            repository (AdminSampleDeletionRepository): Value for ``repository``.

        Returns:
            None.
        """
        cls._repository = repository

    @classmethod
    def has_repository(cls) -> bool:
        """Return whether repository is available.

        Returns:
            bool: The function result.
        """
        return cls._repository is not None

    @classmethod
    def _repo(cls) -> AdminSampleDeletionRepository:
        """Handle  repo.

        Returns:
                The  repo result.
        """
        if cls._repository is None:
            raise RuntimeError("SampleDeletionService repository is not configured")
        return cls._repository


def delete_all_sample_traces(sample_id: str) -> dict[str, object]:
    """Delete all persisted traces for a sample and return summary metadata."""
    sample = SampleDeletionService._repo().get_sample_by_id(sample_id) or {}
    actions = [
        SampleDeletionService._repo().delete_sample_variants,
        SampleDeletionService._repo().delete_sample_cnvs,
        SampleDeletionService._repo().delete_sample_coverage,
        SampleDeletionService._repo().delete_sample_panel_coverage,
        SampleDeletionService._repo().delete_sample_translocs,
        SampleDeletionService._repo().delete_sample_fusions,
        SampleDeletionService._repo().delete_sample_biomarkers,
        SampleDeletionService._repo().delete_sample,
    ]
    results: list[dict[str, object]] = []
    for handler in actions:
        result = handler(sample_id)
        collection_name = handler.__name__.replace("delete_sample_", "").replace("_handler", "")
        if collection_name == "delete_sample":
            collection_name = "sample"
        results.append(
            {
                "collection": collection_name,
                "ok": bool(result),
            }
        )
    return {
        "sample_name": sample.get("name"),
        "results": results,
    }
