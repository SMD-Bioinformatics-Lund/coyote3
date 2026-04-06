"""Sample application service."""

from __future__ import annotations

from typing import Any


class SampleService:
    """Thin service layer around sample persistence operations."""

    @classmethod
    def from_store(cls, store: Any) -> "SampleService":
        """Build the service from the shared store."""
        return cls(sample_handler=store.sample_handler)

    def __init__(self, *, sample_handler: Any) -> None:
        """Create the service with an injected sample handler."""
        self.sample_handler = sample_handler

    def update_filters(self, sample_id: str, filters: dict) -> None:
        """Persist sample filter updates."""
        self.sample_handler.update_sample_filters(sample_id, filters)
