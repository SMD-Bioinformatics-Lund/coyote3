"""Stable assay-group identities and their administrator-facing labels."""

from datetime import datetime

from pydantic import Field, field_validator

from api.config.constants import normalize_clinical_identifier
from api.contracts.schemas.base import _StrictCollectionDocBase, _StrictDocBase


class AssayGroupCreate(_StrictDocBase):
    """Create metadata without accepting system ownership from the client."""

    group_id: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)

    @field_validator("group_id")
    @classmethod
    def canonical_id(cls, value: str) -> str:
        """Normalize the persistent scope key; reject spaces and unsafe characters."""
        return normalize_clinical_identifier(value, label="group_id")

    @field_validator("display_name", "description", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        """Trim display text before enforcing length limits."""
        return value.strip() if isinstance(value, str) else value


class AssayGroupDoc(AssayGroupCreate, _StrictCollectionDocBase):
    """Registered scope; identifiers remain stable for clinical and access references."""

    system_managed: bool = False
    created_by: str
    created_on: datetime
    is_active: bool = True
    version: int = Field(default=1, ge=1)
    publication_serial: int = Field(default=0, ge=0)
    updated_by: str | None = None
    updated_on: datetime | None = None
    status_reason: str = ""


class AssayGroupStatus(_StrictDocBase):
    """Confirmed operational availability change with a concurrency precondition."""

    is_active: bool
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason", mode="before")
    @classmethod
    def trim_reason(cls, value: object) -> object:
        """Reject whitespace-only reasons after trimming."""
        return value.strip() if isinstance(value, str) else value


class AssayGroupImpact(_StrictDocBase):
    """Configuration identities affected by a group status change; no sample data."""

    group: AssayGroupDoc
    assays: list[str]


class AssayGroupsPayload(_StrictDocBase):
    """Registry entries available to assay administrators."""

    groups: list[AssayGroupDoc]
