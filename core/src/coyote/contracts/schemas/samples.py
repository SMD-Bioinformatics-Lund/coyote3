# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Sample document contracts and RNA/DNA consistency rules."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from coyote.config.constants import (
    normalize_asp_family,
    normalize_clinical_identifier,
    normalize_environment,
    normalize_platform,
    normalize_read_mode,
)
from coyote.config.sequencing import resolve_read_technology
from coyote.contracts.sample_manifest import SampleManifest
from coyote.contracts.schemas.base import _CollectionDocBase, _StrictDocBase
from coyote.domain.common.sample_filters import normalize_sample_filters
from coyote.domain.filter_profiles import (
    DnaFilterProfilesDoc,
    RnaFilterProfilesDoc,
)


class SampleCommentRecordDoc(_CollectionDocBase):
    """Sample-level comment with authorship and hiding metadata."""

    sample_oid: Any
    sample_name: str | None = None
    author: str
    text: str
    hidden: int | bool = 0
    hidden_by: str | None = None
    time_created: datetime | None = None
    time_hidden: datetime | None = None


class FindingCommentRecordDoc(_CollectionDocBase):
    """Finding-level comment with retained display identity and hiding metadata."""

    sample_oid: Any
    sample_name: str | None = None
    finding_oid: Any
    finding_type: Literal["small_variant", "cnv", "fusion", "translocation"]
    nomenclature: Literal["p", "c", "g", "cn", "f", "t"] | None = None
    variant: str | None = None
    hgvsp: str | None = None
    hgvsc: str | None = None
    genomic: str | None = None
    genomic_hash: str | None = None
    gene: str | None = None
    transcript: str | None = None
    gene1: str | None = None
    gene2: str | None = None
    author: str
    text: str
    hidden: int | bool = 0
    hidden_by: str | None = None
    time_created: datetime | None = None
    time_hidden: datetime | None = None

    @field_validator("author", mode="before")
    @classmethod
    def _normalize_author(cls, value: Any) -> str:
        """Require a nonblank author after converting the input to text.

        Args:
            value: Author identifier; falsey input is treated as empty.

        Returns:
            The stripped author text.

        Raises:
            ValueError: If the author text is blank.
        """
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("author must be a non-empty string")
        return normalized

    @field_validator("text", mode="before")
    @classmethod
    def _validate_text(cls, value: Any) -> str:
        """Require comment text while preserving the author's whitespace.

        Args:
            value: Nonblank string containing the comment.

        Returns:
            The original string, without trimming.

        Raises:
            ValueError: If input is not a string or contains only whitespace.
        """
        if not isinstance(value, str) or not value.strip():
            raise ValueError("text must be a non-empty string")
        return value


class SampleReportRecordDoc(_CollectionDocBase):
    """Saved report reference with sample scope and filter/configuration snapshots."""

    sample_oid: Any
    sample_name: str | None = None
    asp_id: str | None = None
    diagnosis_id: str | None = None
    environment: str | None = None
    report_num: int
    report_id: str
    report_type: str = "html"
    report_name: str
    filepath: str
    author: str | None = None
    time_created: datetime | None = None
    filters_snapshot: dict[str, Any] = Field(default_factory=dict)
    aspc: dict[str, Any] | None = None
    clinical_rule_source: dict[str, Any] | None = None
    resolution_snapshot: dict[str, Any] | None = None
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    sample_version: int | None = None


class SampleAspcResolutionDoc(_StrictDocBase):
    """Record the selected diagnosis and any Base fallback warning without duplicating context."""

    resolved_diagnosis_id: str
    used_base_configuration: bool = False
    warning: str | None = None

    @classmethod
    def from_resolution(cls, resolution: dict[str, Any]) -> "SampleAspcResolutionDoc":
        """Select persisted resolution details from a complete runtime receipt.

        Args:
            resolution: Resolved diagnosis, fallback flag and optional warning; context is omitted.

        Returns:
            Compact validated sample metadata, independent of runtime context fields.

        Raises:
            ValidationError: The resolved diagnosis is absent or selected metadata is invalid.
        """
        return cls.model_validate(
            {key: resolution[key] for key in cls.model_fields if key in resolution}
        )


class SamplesDoc(SampleManifest, _CollectionDocBase):
    """Sample ingest contract linking clinical scope, files, filters, and case/control metadata."""

    version: int = Field(default=1, ge=1)
    current_aspc_id: Any | None = None
    current_aspc_name: str | None = None
    aspc_resolution: SampleAspcResolutionDoc | None = None
    missing_expected_files: list[str] = Field(
        default_factory=list,
        description="Expected ASP resources unavailable at ingestion; required files block ingestion.",
    )
    filters: DnaFilterProfilesDoc | RnaFilterProfilesDoc | None = None
    ingest_status: Literal["loading", "ready"] = "loading"
    reported: bool = False
    latest_report_id: Any | None = None
    latest_report_on: datetime | None = None
    time_added: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ingested_by: str | None = Field(
        default=None,
        description="Authenticated initial user or machine identity; null if not recorded.",
    )
    ingest_source: Literal["api", "upload", "watcher", "collection_import"] | None = Field(
        default=None,
        description="Initial entry route, assigned by the server; null for unknown history.",
    )

    def to_persistence_document(self) -> dict[str, Any]:
        """Return the canonical application record for a sample.

        Sample documents use a stable shape. Nullable metadata therefore remains
        present as ``None``; omitting it would make "not recorded" indistinguishable
        from an older document that predates the field.
        """
        return self.model_dump(by_alias=True, exclude_none=False)

    @field_validator("asp_id", "diagnosis_id", mode="before")
    @classmethod
    def _normalize_assay_identifiers(cls, value: Any) -> Any:
        """Canonicalize nonnull assay and diagnosis identifiers.

        Args:
            value: Clinical scope identifier, or None.

        Returns:
            Stripped lowercase identifier, or None for later field validation.

        Raises:
            ValueError: If a nonnull identifier is blank or contains unsupported characters.
        """
        if value is None:
            return None
        return normalize_clinical_identifier(value, label="clinical scope identifier")

    @field_validator("environment", mode="before")
    @classmethod
    def _normalize_profile(cls, value: Any) -> Any:
        """Validate a nonnull environment against the configured vocabulary.

        Args:
            value: Environment label, or None for later required-field validation.

        Returns:
            Canonical lowercase environment, or None.

        Raises:
            ValueError: If a nonnull environment is blank or unsupported.
        """
        if value is None:
            return None
        return normalize_environment(value, label="environment")

    @field_validator("asp_family", mode="before")
    @classmethod
    def _normalize_asp_family(cls, value: Any) -> str:
        """Validate the sample's technical assay family.

        Args:
            value: Scope label before whitespace and case normalization.

        Returns:
            The canonical configured scope.

        Raises:
            ValueError: If the scope is blank or unsupported.
        """
        return normalize_asp_family(value)

    @field_validator("platform", mode="before")
    @classmethod
    def _normalize_platform(cls, value: Any) -> str | None:
        """Canonicalize an optional sequencing platform.

        Args:
            value: Platform name; null and blank input mean unspecified.

        Returns:
            Canonical lowercase platform, or None for unspecified input.

        Raises:
            ValueError: If a nonblank platform is unsupported.
        """
        return normalize_platform(value)

    @field_validator("read_mode", mode="before")
    @classmethod
    def _normalize_read_mode(cls, value: Any) -> str | None:
        """Canonicalize an optional sequencing read mode.

        Args:
            value: Read mode; null and blank input mean unspecified.

        Returns:
            Canonical uppercase read mode, or None for unspecified input.

        Raises:
            ValueError: If a nonblank mode is unsupported.
        """
        return normalize_read_mode(value)

    @model_validator(mode="after")
    def _derive_platform_capabilities(self) -> "SamplesDoc":
        """Validate read mode and set technology from the platform vocabulary.

        Returns:
            This sample with derived read_technology.

        Raises:
            ValueError: If read mode is incompatible or an explicitly supplied technology
                conflicts with the platform-derived value.
        """
        self.read_technology = resolve_read_technology(
            self.platform, self.read_mode, self.read_technology
        )
        return self

    @model_validator(mode="before")
    @classmethod
    def _normalize_sample_shape(cls, data: Any) -> Any:
        """Discard embedded history and normalize clinical filter profiles.

        Args:
            data: Raw sample dictionary; other inputs pass through.

        Returns:
            A shallow copy with embedded comments/report fields removed and canonical
            clinical filters. Missing reported is derived from latest_report_id.

        Raises:
            ValueError: If supplied filters violate the canonical intent-aware contract.
        """
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        normalized.pop("comments", None)
        normalized.pop("reports", None)
        normalized.pop("report_num", None)
        if "reported" not in normalized:
            normalized["reported"] = bool(normalized.get("latest_report_id"))

        if normalized.get("filters") is not None:
            normalized["filters"] = normalize_sample_filters(
                normalized.get("filters"),
                asp_category=str(normalized.get("asp_category") or "dna"),
                analysis_intents=normalized.get("analysis_intents"),
                canonical=True,
            )
        return normalized

    @model_validator(mode="after")
    def _validate_intent_filter_capabilities(self) -> "SamplesDoc":
        """Check germline availability and the presence of its SNV filter profile.

        Returns:
            This sample unchanged; absent filters bypass profile-presence checks.

        Raises:
            ValueError: If RNA requests germline, supplied filters lack germline SNV
                for a germline intent, or germline filters exist without that intent.
        """
        if self.asp_category == "rna" and "germline" in self.analysis_intents:
            raise ValueError("germline analysis is currently supported only for DNA SNV")
        if self.filters is None:
            return self
        dumped = self.filters.model_dump(exclude_none=True)
        if "germline" in self.analysis_intents:
            germline = dumped.get("germline") or {}
            if not germline.get("snv"):
                raise ValueError("germline analysis requires filters.germline.snv")
        elif dumped.get("germline"):
            raise ValueError("filters.germline requires germline in analysis_intents")
        return self
