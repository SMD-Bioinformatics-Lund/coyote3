"""Sample application service."""

from __future__ import annotations

from typing import Any


class SampleService:
    """Thin service layer around sample persistence operations."""

    @classmethod
    def from_store(cls, store: Any) -> "SampleService":
        """Build the service from the runtime store."""
        return cls(sample_repository=store.sample_repository)

    def __init__(self, *, sample_repository: Any) -> None:
        """Create the service with an injected sample repository."""
        self.sample_repository = sample_repository

    def update_filters(self, sample_id: str, filters: dict) -> None:
        """Persist sample filter updates."""
        self.sample_repository.update_sample_filters(sample_id, filters)
