"""Sample application service."""

from __future__ import annotations

from api.core.samples.ports import SamplesRepository
from api.extensions import store


class SampleService:
    """Thin service layer around sample persistence operations."""

    def __init__(self, repository: SamplesRepository | None = None) -> None:
        """Build the service with a sample mutation repository."""
        self.repository = repository or store.get_sample_repository()

    def update_filters(self, sample_id: str, filters: dict) -> None:
        """Update filters.

        Args:
            sample_id (str): Value for ``sample_id``.
            filters (dict): Value for ``filters``.

        Returns:
            None.
        """
        self.repository.update_sample_filters(sample_id, filters)
