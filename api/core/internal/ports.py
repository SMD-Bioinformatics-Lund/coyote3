"""Repository ports for internal utility and ingest endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class InternalRepository(Protocol):
    """Define the persistence operations required by internal support routes."""

    def get_all_roles(self) -> list[dict]:
        """Return all roles.

        Returns:
            list[dict]: The function result.
        """
        ...

    def is_isgl_adhoc(self, isgl_id: str) -> bool:
        """Return whether isgl adhoc is true.

        Args:
            isgl_id (str): Value for ``isgl_id``.

        Returns:
            bool: The function result.
        """
        ...

    def get_isgl_display_name(self, isgl_id: str) -> str | None:
        """Return isgl display name.

        Args:
            isgl_id (str): Value for ``isgl_id``.

        Returns:
            str | None: The function result.
        """
        ...


@dataclass(frozen=True)
class ReplaceDocumentResult:
    """Summarize a replace-one persistence operation."""

    matched_count: int
    modified_count: int
    upserted_id: str | None = None


class InternalIngestRepository(Protocol):
    """Define the persistence operations required by internal ingest workflows."""

    def list_samples_by_exact_name(self, name: str) -> list[dict[str, Any]]:
        """Return samples whose name matches exactly."""
        ...

    def list_samples_by_name_pattern(self, name_pattern: str) -> list[dict[str, Any]]:
        """Return samples whose name matches the supplied pattern."""
        ...

    def list_refseq_canonical_documents(self) -> list[dict[str, Any]]:
        """Return refseq canonical documents used during ingest parsing."""
        ...

    def find_sample_by_name(self, name: str) -> dict[str, Any] | None:
        """Return one sample document by name."""
        ...

    def find_sample_by_id(self, sample_id: str) -> dict[str, Any] | None:
        """Return one sample document by id."""
        ...

    def new_sample_id(self) -> str:
        """Return a new provider-native sample id serialized for the app layer."""
        ...

    def insert_sample(self, document: dict[str, Any]) -> str:
        """Insert one sample document and return its stored id."""
        ...

    def update_sample_fields(self, sample_id: str, fields: dict[str, Any]) -> None:
        """Apply a partial update to one sample document."""
        ...

    def delete_sample(self, sample_id: str) -> None:
        """Delete one sample document by id."""
        ...

    def list_collection_documents(
        self, collection: str, match: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Return documents from a supported ingest collection."""
        ...

    def delete_collection_documents(self, collection: str, match: dict[str, Any]) -> None:
        """Delete documents from a supported ingest collection."""
        ...

    def insert_collection_document(
        self, collection: str, document: dict[str, Any], *, ignore_duplicate: bool = False
    ) -> str | None:
        """Insert one document into a supported ingest collection."""
        ...

    def insert_collection_documents(
        self,
        collection: str,
        documents: list[dict[str, Any]],
        *,
        ignore_duplicates: bool = False,
    ) -> int:
        """Insert many documents into a supported ingest collection."""
        ...

    def replace_collection_document(
        self,
        collection: str,
        *,
        match: dict[str, Any],
        document: dict[str, Any],
        upsert: bool = False,
    ) -> ReplaceDocumentResult:
        """Replace one document in a supported ingest collection."""
        ...
