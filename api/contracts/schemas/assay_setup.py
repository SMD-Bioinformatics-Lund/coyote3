"""Saved assay setup workspaces, separate from operational assay documents."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from api.config.constants import (
    SUBPANEL_BASE_ID,
    normalize_clinical_identifier,
    normalize_environment,
)
from api.contracts.schemas.assay import AssaySpecificPanelsDoc
from api.contracts.schemas.base import _StrictCollectionDocBase, _StrictDocBase


class AssaySetupContent(_StrictDocBase):
    """Assay definition and staged resources; Base is always an implicit scope."""

    panel: AssaySpecificPanelsDoc
    scopes: list[str] = Field(default_factory=lambda: [SUBPANEL_BASE_ID], max_length=100)
    environments: list[str] = Field(default_factory=list, max_length=20)
    gene_lists: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    configurations: list[dict[str, Any]] = Field(default_factory=list, max_length=200)

    @field_validator("panel", mode="before")
    @classmethod
    def discard_display_counts(cls, value: Any) -> Any:
        """Ignore derived response counts when a client resubmits an assay form."""
        if isinstance(value, dict):
            return {
                key: item
                for key, item in value.items()
                if key not in {"covered_genes_count", "germline_genes_count"}
            }
        return value

    @field_validator("scopes")
    @classmethod
    def canonical_scopes(cls, values: list[str]) -> list[str]:
        """Include Base once and canonicalize optional named scope identifiers."""
        return list(
            dict.fromkeys([SUBPANEL_BASE_ID, *(normalize_clinical_identifier(v) for v in values)])
        )

    @field_validator("environments")
    @classmethod
    def canonical_environments(cls, values: list[str]) -> list[str]:
        """Validate and deduplicate the environments selected for activation."""
        return list(dict.fromkeys(normalize_environment(v) for v in values))


class AssaySetupUpdate(_StrictDocBase):
    """Replace draft content only at the revision the editor loaded."""

    revision: int = Field(ge=1)
    content: AssaySetupContent


class AssaySetupAction(_StrictDocBase):
    """Concurrency precondition and review explanation."""

    revision: int = Field(ge=1)
    reason: str = Field(default="", max_length=2000)


class AssaySetupDoc(_StrictCollectionDocBase):
    """Governed setup draft; publication leaves its final content immutable."""

    asp_id: str
    content: AssaySetupContent
    status: Literal["draft", "submitted", "published"] = "draft"
    revision: int = Field(default=1, ge=1)
    content_editors: list[str]
    created_by: str
    created_at: datetime
    updated_by: str
    updated_at: datetime
    review_reason: str = ""
    published_by: str | None = None
    review_dependencies: str | None = None


class AssaySetupRevisionDoc(_StrictCollectionDocBase):
    """Immutable full snapshot for one setup revision."""

    setup_id: str
    revision: int
    action: str
    document: AssaySetupDoc


class AssaySetupListPayload(_StrictDocBase):
    """Saved workspace summaries without their configuration content."""

    items: list[dict[str, Any]]


class AssaySetupContextPayload(_StrictDocBase):
    """Managed forms and readiness for a new or existing setup."""

    panel_form: dict[str, Any]
    subpanels: list[dict[str, Any]]
    environments: list[str]
    setup: AssaySetupDoc | None = None
    genelist_form: dict[str, Any] | None = None
    configuration_form: dict[str, Any] | None = None
    context_error: str | None = None
    history: list[dict[str, Any]] = Field(default_factory=list)
    rules: list[dict[str, Any]] = Field(default_factory=list)
    readiness: dict[str, Any] | None = None
