# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Common application record contract primitives."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from coyote.config.factory_defaults import factory_value


class _DocBase(BaseModel):
    """Permissive base for application records.

    Contracts intentionally allow unknown keys to support additive, non-breaking
    field growth while known keys remain typed and validated.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)


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
    system_installed: bool = Field(
        default=factory_value("records.system_installed"), exclude_if=lambda value: not value
    )


class _DataDocBase(_DocBase):
    """Clinical data attribution, without installation ownership flags."""

    created_by: str | None = Field(default=None, exclude_if=lambda value: value is None)
    updated_by: str | None = Field(default=None, exclude_if=lambda value: value is None)

    @model_validator(mode="before")
    @classmethod
    def _remove_installation_flag(cls, data: Any) -> Any:
        """Discard obsolete installation metadata without mutating input."""
        if not isinstance(data, dict):
            return data
        return {key: value for key, value in data.items() if key != "system_installed"}


class _StrictDataDocBase(_DataDocBase):
    """Clinical data with a strict contract and a Mongo identity alias."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    id_: Any | None = Field(default=None, alias="_id")


class _FindingDocBase(_DataDocBase):
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
    """Strict base for application records with stable identity aliases."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id_: Any | None = Field(default=None, alias="_id")
