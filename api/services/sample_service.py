"""Sample application service."""

from __future__ import annotations

from api.repositories.sample_repository import SampleRepository


class SampleService:
    """Thin service layer around sample persistence operations."""

    def __init__(self, repository: SampleRepository | None = None) -> None:
        self.repository = repository or SampleRepository()

    def update_filters(self, sample_id: str, filters: dict) -> None:
        self.repository.update_sample_filters(sample_id, filters)
