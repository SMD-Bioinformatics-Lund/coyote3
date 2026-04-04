"""Ports for shared interpretation helpers."""

from __future__ import annotations

from typing import Any, Protocol


class InterpretationRepository(Protocol):
    """Define persistence operations required by interpretation helpers."""

    def new_comment_id(self) -> Any:
        """Return a new identifier suitable for embedded comment documents."""
        ...

    def get_additional_classifications(
        self, variant: dict, assay: str, subpanel: str
    ) -> list[dict]:
        """Return additional classifications for a variant or fusion."""
        ...

    def get_global_annotations(
        self, variant: dict, assay: str, subpanel: str
    ) -> tuple[list, dict | None, list, list]:
        """Return annotations and classifications for a variant or fusion."""
        ...

    def get_samples_by_oids(self, sample_oids: list[object]) -> list[dict]:
        """Return samples matching the given repository-native identifiers."""
        ...

    def list_annotations_by_ids(self, annotation_ids: list[object]) -> list[dict]:
        """Return annotation documents matching the given repository-native identifiers."""
        ...
