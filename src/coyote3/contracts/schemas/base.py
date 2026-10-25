"""Common DB document contract primitives."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _DocBase(BaseModel):
    """Permissive base for MongoDB documents.

    Contracts intentionally allow unknown keys to support additive, non-breaking
    field growth while known keys remain typed and validated.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _normalize_extended_json_dates(cls, data: Any) -> Any:
        """Normalize Mongo extended JSON date objects into plain values."""
        if isinstance(data, dict):
            normalized: dict[str, Any] = {}
            for key, value in data.items():
                if isinstance(value, dict) and "$date" in value:
                    normalized[key] = value.get("$date")
                elif isinstance(value, list):
                    normalized[key] = [
                        item.get("$date") if isinstance(item, dict) and "$date" in item else item
                        for item in value
                    ]
                else:
                    normalized[key] = value
            return normalized
        return data


class _StrictDocBase(_DocBase):
    """Strict base for embedded documents with a fixed key-level contract."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class _CollectionDocBase(_DocBase):
    """Persisted record attribution assigned by trusted application workflows.

    Null actors represent missing historical evidence, never an inferred user.
    Creation attribution is retained when a record is revised.
    Absent attribution defaults are omitted on serialization so reading historical
    records does not change their persisted shape or immutable snapshot digests.
    """

    created_by: str | None = Field(default=None, exclude_if=lambda value: value is None)
    updated_by: str | None = Field(default=None, exclude_if=lambda value: value is None)
    system_installed: bool = Field(default=False, exclude_if=lambda value: not value)


class _FindingDocBase(_CollectionDocBase):
    """Finding document base that prevents embedded comment persistence."""

    @model_validator(mode="before")
    @classmethod
    def _remove_embedded_comments(cls, data: Any) -> Any:
        """Remove embedded comments from raw finding dictionaries.

        Args:
            data: Raw finding input; non-dictionaries pass through.

        Returns:
            A shallow copy without comments, or the non-dictionary input unchanged.
        """
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        normalized.pop("comments", None)
        return normalized


class _StrictCollectionDocBase(_CollectionDocBase):
    """Strict base for top-level MongoDB collection documents."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id_: Any | None = Field(default=None, alias="_id")
