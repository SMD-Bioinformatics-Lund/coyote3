# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Structural sample manifests shared by pipeline tools and clinical hosts.

Center vocabulary, sequencing policy and clinical filter validation belong to the
consuming clinical host. A valid manifest is not an authorization or acceptance decision.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from coyote.contracts.database_versions import normalize_database_versions
from coyote.contracts.manifests import MANIFEST_FILE_KEYS, normalize_manifest_files

DNA_SAMPLE_FILE_KEYS = MANIFEST_FILE_KEYS["dna"]
RNA_SAMPLE_FILE_KEYS = MANIFEST_FILE_KEYS["rna"]


class ManifestObject(BaseModel):
    """Permit additive input metadata while validating declared fields."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class ManifestFileObject(ManifestObject):
    """Reject undeclared fields in an individual file descriptor."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class SampleCaseControlDoc(ManifestObject):
    """Alignment paths and sequencing metadata for one case or control."""

    bam: str = ""
    bai: str = ""
    id: str | None = None
    clarity_id: str | None = None
    clarity_pool_id: str | None = None
    ffpe: bool = False
    sequencing_run: str | list[str] | None = Field(
        default=None,
        description="One sequencing run, or multiple nonfailed runs confirmed for this specimen.",
    )
    reads: int | None = None
    purity: float | None = None

    @field_validator("bam", "bai", mode="before")
    @classmethod
    def _normalize_alignment_paths(cls, value: Any) -> Any:
        """Normalize optional BAM and index path text.

        Args:
            value: Alignment path; None means no path.

        Returns:
            An empty string for None, stripped text for strings, or other input unchanged.
        """
        if value is None:
            return ""
        return value.strip() if isinstance(value, str) else value


class SampleFileDoc(ManifestFileObject):
    """Registered sample file path with optional checksum, byte size, and timestamp."""

    path: str
    checksum: str | None = None
    size_bytes: int | None = None
    registered_on: datetime | None = None

    @field_validator("path", "checksum", mode="before")
    @classmethod
    def _strip_optional_strings(cls, value: Any) -> Any:
        """Convert file path or checksum input to stripped text.

        Args:
            value: Path or checksum value; null and whitespace-only input mean missing.

        Returns:
            Stripped text, or None for missing input. Required-field validation
            subsequently rejects a missing path.
        """
        if value is None:
            return None
        value = str(value).strip()
        return value or None


class SampleManifest(ManifestObject):
    """Validate portable manifest structure without loading application policy."""

    name: str
    asp_id: str
    diagnosis_id: str | None = None
    environment: str
    genome_build: int | None = None
    database_versions: dict[str, str] = Field(default_factory=dict)
    case_id: str
    control_id: str | None = None
    sample_no: int
    paired: bool | None = False
    asp_family: str
    asp_category: Literal["dna", "rna"]
    sex: Literal["female", "male", "unknown"] | None = None
    platform: str | None = None
    read_mode: str | None = None
    read_technology: str | None = None
    pipeline: str
    pipeline_version: str | None = None
    files: dict[str, SampleFileDoc] = Field(default_factory=dict)
    analysis_intents: list[str] = Field(default_factory=lambda: ["somatic"])
    case: SampleCaseControlDoc = Field(default_factory=SampleCaseControlDoc)
    control: SampleCaseControlDoc | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_manifest_files(cls, data: Any) -> Any:
        """Collect declared file paths and checksums into canonical file descriptors."""
        return normalize_manifest_files(data)

    @model_validator(mode="before")
    @classmethod
    def _reject_retired_version_fields(cls, value: Any) -> Any:
        """Reject retired sample fields rather than silently accepting two shapes."""
        if not isinstance(value, dict):
            return value
        retired_keys = {
            "omics_layer",
            "sequencing_scope",
            "current_aspc_key",
            "current_aspc_version",
            "assay",
            "profile",
            "diagnosis",
            "subpanel",
            "subpanel_id",
            "sequencing_technology",
            "vep_version",
            "db_versions",
            "reference_versions",
            "annotation_versions",
        }
        present = sorted(retired_keys.intersection(value))
        if present:
            raise ValueError(
                "Retired sample fields are not accepted: "
                + ", ".join(present)
                + ". Use asp_id, diagnosis_id, environment, platform, and database_versions."
            )
        return value

    @field_validator("asp_family", "asp_category", mode="before")
    @classmethod
    def _normalize_lowercase(cls, value: Any) -> Any:
        """Trim and lowercase assay family or category strings.

        Args:
            value: Raw scope or layer input.

        Returns:
            Stripped lowercase text for strings, otherwise the input unchanged.
        """
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("sex", mode="before")
    @classmethod
    def _normalize_sex(cls, value: Any) -> str | None:
        """Normalize an optional sex label before literal-choice validation.

        Args:
            value: Label value; null or blank input means unspecified.

        Returns:
            Stripped lowercase text, or None for unspecified input.
        """
        if value is None:
            return None
        normalized = str(value).strip().lower()
        return normalized or None

    @field_validator("database_versions", mode="before")
    @classmethod
    def _normalize_database_versions(cls, value: Any) -> dict[str, str]:
        """Validate database-version keys and remove missing-version markers.

        Args:
            value: Mapping of canonical database keys to versions; None gives an empty mapping.

        Returns:
            Stripped version strings with missing markers omitted and leading v/V
            characters removed from VEP versions.

        Raises:
            ValueError: If input is not a mapping or contains an unsupported database key.
        """
        return normalize_database_versions(value)

    @field_validator("pipeline_version", mode="before")
    @classmethod
    def _normalize_pipeline_version(cls, value: Any) -> str | None:
        """Treat blank and not-provided pipeline version labels as missing.

        Args:
            value: Version value; not provided may use spaces, underscores, or hyphens
                and any letter case.

        Returns:
            Stripped version text, or None for null, blank, or not-provided input.
        """
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower().replace("_", " ").replace("-", " ") == "not provided":
            return None
        return text

    @field_validator("analysis_intents", mode="before")
    @classmethod
    def _normalize_analysis_intents(cls, value: Any) -> list[str]:
        """Canonicalize and deduplicate sample analysis intents.

        Args:
            value: Intent or list of intents; blank selections default to somatic.

        Returns:
            Somatic and/or germline intent names in first-occurrence order.

        Raises:
            ValueError: If a nonblank intent is neither somatic nor germline.
        """
        values = value if isinstance(value, list) else [value]
        normalized = list(
            dict.fromkeys(
                str(item or "").strip().lower() for item in values if str(item or "").strip()
            )
        )
        if not normalized:
            return ["somatic"]
        invalid = [item for item in normalized if item not in {"somatic", "germline"}]
        if invalid:
            raise ValueError("analysis_intents may contain only somatic and germline")
        return normalized

    @field_validator("case_id", "control_id", "name", "asp_id", "pipeline", mode="before")
    @classmethod
    def _strip_strings(cls, value: Any) -> Any:
        """Trim sample identity text and turn blank strings into null.

        Args:
            value: Case/control ID, sample name, assay ID, or pipeline value.

        Returns:
            Stripped nonblank strings, None for blank strings, or nonstrings unchanged.
        """
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @model_validator(mode="after")
    def _validate_case_control_consistency(self) -> "SampleManifest":
        """Check identifiers, pairing status, and declared sample count together.

        Returns:
            This sample unchanged.

        Raises:
            ValueError: If case_id is empty, case and control IDs coincide, a single
                case has paired status, count other than one, or control details,
                or a case/control pair lacks paired=True and sample_no=2.
        """
        has_case = bool(self.case_id)
        has_control = bool(self.control_id)

        if not has_case:
            raise ValueError("case_id is required")

        if has_control and self.case_id == self.control_id:
            raise ValueError("case_id and control_id must not be the same")

        # Tumor-only / single-sample case
        if has_case and not has_control:
            if self.paired not in (False, None):
                raise ValueError("paired must be False or None when control_id is missing")
            if self.sample_no != 1:
                raise ValueError("sample_no must be 1 when only case_id is present")

            if self.control is not None:
                raise ValueError("control details must not be provided when control_id is missing")

        # Paired case-control sample
        if has_case and has_control:
            if self.paired is not True:
                raise ValueError("paired must be True when control_id is present")
            if self.sample_no != 2:
                raise ValueError("sample_no must be 2 when both case_id and control_id are present")

        return self

    @model_validator(mode="after")
    def _validate_omics_payload_consistency(self) -> "SampleManifest":
        """Check that registered data file keys agree with the sample's omics layer.

        Returns:
            This sample unchanged.

        Raises:
            ValueError: If DNA includes an RNA file key, RNA includes a DNA file key,
                or no file key belonging to the selected layer is present.

        Notes:
            Membership is checked against the configured key sets, not file existence.
        """
        present_keys = set(self.files)
        has_dna = any(key in present_keys for key in DNA_SAMPLE_FILE_KEYS)
        has_rna = any(key in present_keys for key in RNA_SAMPLE_FILE_KEYS)

        if self.asp_category == "dna":
            if has_rna:
                raise ValueError(
                    "DNA sample must not include RNA file keys "
                    "(fusion_files/expression_path/classification_path/qc)"
                )
            if not has_dna:
                raise ValueError("DNA sample must include at least one DNA data file key")
        elif self.asp_category == "rna":
            if has_dna:
                raise ValueError(
                    "RNA sample must not include DNA file keys "
                    "(vcf_files/cnv/cov/biomarkers/transloc)"
                )
            if not has_rna:
                raise ValueError("RNA sample must include at least one RNA data file key")
        return self
