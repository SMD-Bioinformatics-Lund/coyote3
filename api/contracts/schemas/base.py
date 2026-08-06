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
    """Strict base for collections where we want full key-level contract lock."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    id_: Any | None = Field(default=None, alias="_id")
