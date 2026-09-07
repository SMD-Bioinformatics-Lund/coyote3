"""Persistence contracts for center-owned public assay catalog content."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

import bleach
from pydantic import ConfigDict, Field, field_validator, model_validator

from api.config.constants import normalize_clinical_identifier
from api.contracts.schemas.base import _StrictCollectionDocBase, _StrictDocBase


def clean_catalog_html(value: str) -> str:
    """Keep public document formatting without executable or embedded content."""
    return bleach.clean(
        value,
        tags={
            "p",
            "br",
            "strong",
            "em",
            "b",
            "i",
            "u",
            "ul",
            "ol",
            "li",
            "a",
            "table",
            "thead",
            "tbody",
            "tr",
            "td",
            "th",
            "blockquote",
            "code",
            "pre",
            "h2",
            "h3",
            "h4",
            "span",
            "div",
            "hr",
            "sub",
            "sup",
        },
        attributes={
            "a": ["href", "title"],
            "td": ["colspan", "rowspan"],
            "th": ["colspan", "rowspan"],
        },
        protocols={"http", "https", "mailto"},
        strip=True,
    )


class _PublicCatalogTextDoc(_StrictDocBase):
    @model_validator(mode="after")
    def sanitize_public_html(self):
        for name in ("description", "limitations", "public_notes"):
            value = getattr(self, name, None)
            if isinstance(value, str):
                setattr(self, name, clean_catalog_html(value))
        # Additional scalar presentation fields are rendered as HTML by the catalog.
        for name, value in (self.__pydantic_extra__ or {}).items():
            if isinstance(value, str):
                self.__pydantic_extra__[name] = clean_catalog_html(value)
        return self


class PublicCatalogPresentationDoc(_PublicCatalogTextDoc):
    """Editable public wording shared by entries and gene-list descriptions."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)
    label: str | None = None
    title: str | None = None
    description: str | None = None
    subheading: str | None = None
    input_material: list[str] = Field(default_factory=list)
    sample_modes: list[str] = Field(default_factory=list)
    analysis: list[str] = Field(default_factory=list)
    report_sections: list[str] = Field(default_factory=list)
    clinical_indications: list[str] = Field(default_factory=list)
    tat: str = ""
    limitations: str | None = None
    public_notes: str | None = None

    @field_validator("tat")
    @classmethod
    def validate_turnaround(cls, value: str) -> str:
        value = value.strip()
        if not value:
            return value
        match = re.fullmatch(r"([1-9]\d*)(?:-([1-9]\d*))? (days?|weeks?|months?|years?)", value)
        if not match or (match[2] and int(match[1]) > int(match[2])):
            raise ValueError("Use a positive duration or ascending range, such as 7-10 days")
        return value


class PublicCatalogGeneListDoc(PublicCatalogPresentationDoc):
    isgl_id: str | None = None
    key: str | None = None


class PublicCatalogCategoryDoc(PublicCatalogPresentationDoc):
    """Presentation metadata for one public ASP/ASPC category.

    The public catalog deliberately permits additional presentation fields so
    centers can extend wording without changing clinical collection contracts.
    """

    catalog_id: str | None = None
    asp_id: str | None = None
    aspc_id: str | None = None
    subpanel_id: str | None = None
    aspc_ids: dict[str, str] = Field(default_factory=dict)
    gene_lists: list[PublicCatalogGeneListDoc] = Field(default_factory=list)

    @field_validator("catalog_id", "asp_id", "aspc_id", "subpanel_id", mode="before")
    @classmethod
    def normalize_optional_identifier(cls, value: Any) -> str | None:
        if value is None or not str(value).strip():
            return None
        return normalize_clinical_identifier(value, label="public catalog identifier")


class PublicCatalogModalityDoc(_PublicCatalogTextDoc):
    """Presentation metadata and categories for one DNA/RNA modality."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    label: str | None = None
    title: str | None = None
    description: str | None = None
    categories: dict[str, PublicCatalogCategoryDoc] = Field(default_factory=dict)


class PublicCatalogLayoutDoc(_StrictDocBase):
    """Display order for configured modalities."""

    order: list[str] = Field(default_factory=list)

    @field_validator("order", mode="before")
    @classmethod
    def normalize_order(cls, value: Any) -> list[str]:
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError("order must be a list of section keys")
        values = value
        return list(
            dict.fromkeys(str(item).strip().lower() for item in values if str(item).strip())
        )


class PublicAssayCatalogDoc(_StrictCollectionDocBase):
    """One center-owned public catalog document stored in the primary database."""

    catalog_id: Literal["default"] = "default"
    schema_version: Literal[1] = 1
    version: int = Field(default=1, ge=1)
    header: str = "Assay Catalog"
    description: str = ""
    maintainer: str | None = None
    layout: PublicCatalogLayoutDoc = Field(default_factory=PublicCatalogLayoutDoc)
    modalities: dict[str, PublicCatalogModalityDoc] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = "system"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: str = "system"

    @field_validator("description")
    @classmethod
    def sanitize_description(cls, value: str) -> str:
        return clean_catalog_html(value)

    @field_validator("modalities", mode="before")
    @classmethod
    def normalize_modalities(cls, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("modalities must be an object")
        normalized = {str(key).strip().lower(): item for key, item in value.items()}
        if "" in normalized or len(normalized) != len(value):
            raise ValueError("section keys must be nonempty and unique ignoring case")
        return normalized


class PublicCatalogModalityExport(_StrictDocBase):
    """Portable JSON envelope for one catalog modality."""

    kind: Literal["coyote3.public_assay_catalog_modality"]
    schema_version: Literal[1] = 1
    modality: str
    definition: PublicCatalogModalityDoc

    @field_validator("modality")
    @classmethod
    def normalize_modality(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("modality cannot be empty")
        return normalized


class PublicCatalogStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


class PublicCatalogReviewDoc(_StrictDocBase):
    submitted_by: str | None = None
    submitted_at: datetime | None = None
    reviewer: str | None = None
    reviewer_decision_at: datetime | None = None
    reviewer_reason: str | None = None
    publisher: str | None = None


class PublicCatalogLifecycleEvent(_StrictDocBase):
    action: str
    actor: str
    occurred_at: datetime
    reason: str | None = None


class PublicAssayCatalogVersionDoc(_StrictCollectionDocBase):
    """A draft or immutable published version of the public assay catalog."""

    catalog_key: Literal["default"] = "default"
    schema_version: Literal[1] = 1
    content_version: int | None = Field(default=None, ge=1)
    base_version: int = Field(default=0, ge=0)
    content_editors: list[str] = Field(default_factory=list)
    revision: int = Field(ge=1)
    status: PublicCatalogStatus
    catalog: PublicAssayCatalogDoc
    review: PublicCatalogReviewDoc = Field(default_factory=PublicCatalogReviewDoc)
    lifecycle: list[PublicCatalogLifecycleEvent] = Field(default_factory=list)
    change_summary: str = ""
    created_at: datetime
    created_by: str
    updated_at: datetime
    updated_by: str
    published_at: datetime | None = None
    published_by: str | None = None


class PublicCatalogRevisionDoc(_StrictCollectionDocBase):
    version_id: str
    revision: int = Field(ge=1)
    document: PublicAssayCatalogVersionDoc
