"""Sample document contracts and RNA/DNA consistency rules."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from api.config.constants import (
    ALL_SAMPLE_FILE_KEYS,
    SAMPLE_FILE_KEYS,
    normalize_clinical_identifier,
    normalize_environment,
    normalize_platform,
    normalize_read_mode,
    normalize_sequencing_scope,
)
from api.config.database_versions import normalize_database_versions
from api.config.sequencing import derived_read_technology, validate_platform_read_mode
from api.contracts.schemas.base import _DocBase, _StrictDocBase
from api.contracts.schemas.filter_profiles import (
    CnvFiltersDoc,
    CoverageFiltersDoc,
    DnaFilterProfilesDoc,
    FusionFiltersDoc,
    RnaFilterProfilesDoc,
    SnvFiltersDoc,
)
from api.domain.common.sample_filters import normalize_sample_filters

DNA_SAMPLE_FILE_KEYS: tuple[str, ...] = SAMPLE_FILE_KEYS["dna"]
RNA_SAMPLE_FILE_KEYS: tuple[str, ...] = SAMPLE_FILE_KEYS["rna"]
SAMPLE_SOURCE_PATH_KEYS: tuple[str, ...] = ALL_SAMPLE_FILE_KEYS


class SampleCaseControlDoc(_DocBase):
    """Alignment paths and sequencing metadata for one case or control."""

    bam: str = ""
    bai: str = ""
    id: str | None = None
    clarity_id: str | None = None
    clarity_pool_id: str | None = None
    ffpe: bool = False
    sequencing_run: str | None = None
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


class SampleFileDoc(_StrictDocBase):
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


class SampleCommentRecordDoc(_DocBase):
    """Sample-level comment with authorship and hiding metadata."""

    sample_oid: Any
    sample_name: str | None = None
    author: str
    text: str
    hidden: int | bool = 0
    hidden_by: str | None = None
    time_created: datetime | None = None
    time_hidden: datetime | None = None


class FindingCommentRecordDoc(_DocBase):
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


class SampleReportRecordDoc(_DocBase):
    """Saved report reference with sample scope and filter/configuration snapshots."""

    sample_oid: Any
    sample_name: str | None = None
    asp_id: str | None = None
    subpanel_id: str | None = None
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


class SampleAspcResolutionDoc(_StrictDocBase):
    """Persisted resolution between a sample scope and its applied ASPC."""

    requested_subpanel_id: str
    resolved_subpanel_id: str
    used_base_configuration: bool = False
    resolved_from_sample_revision: bool = False
    warning: str | None = None

    @field_validator("requested_subpanel_id", "resolved_subpanel_id", mode="before")
    @classmethod
    def _normalize_scope_identifier(cls, value: Any) -> str:
        """Canonicalize a requested or resolved subpanel identifier.

        Args:
            value: Required subpanel identifier.

        Returns:
            Stripped lowercase identifier with hyphens and underscores preserved.

        Raises:
            ValueError: If blank or containing unsupported characters.
        """
        return normalize_clinical_identifier(value, label="subpanel_id")


# Public aliases retain the useful domain names for consumers of this contract.
SampleDnaSnvFiltersDoc = SnvFiltersDoc
SampleDnaCnvFiltersDoc = CnvFiltersDoc
SampleCoverageFiltersDoc = CoverageFiltersDoc
SampleRnaFusionFiltersDoc = FusionFiltersDoc
SampleDnaFiltersDoc = DnaFilterProfilesDoc
SampleRnaFiltersDoc = RnaFilterProfilesDoc


class SamplesDoc(_DocBase):
    """Sample ingest contract linking clinical scope, files, filters, and case/control metadata."""

    name: str
    asp_id: str
    subpanel_id: str | None = None
    environment: str
    current_aspc_id: Any | None = None
    current_aspc_key: str | None = None
    current_aspc_version: int | None = None
    aspc_resolution: SampleAspcResolutionDoc | None = None
    genome_build: int | None = None
    database_versions: dict[str, str] = Field(default_factory=dict)
    case_id: str
    control_id: str | None = None
    sample_no: int
    paired: bool | None = False
    sequencing_scope: str
    omics_layer: Literal["dna", "rna"]
    sex: Literal["female", "male", "unknown"] | None = None
    platform: str | None = None
    read_mode: str | None = None
    read_technology: str | None = None
    pipeline: str
    pipeline_version: str | None = None
    files: dict[str, SampleFileDoc] = Field(default_factory=dict)
    analysis_intents: list[str] = Field(default_factory=lambda: ["somatic"])
    filters: SampleDnaFiltersDoc | SampleRnaFiltersDoc | None = None
    case: SampleCaseControlDoc = Field(default_factory=SampleCaseControlDoc)
    control: SampleCaseControlDoc | None = None
    ingest_status: Literal["loading", "ready"] = "loading"
    reported: bool = False
    latest_report_id: Any | None = None
    latest_report_on: datetime | None = None
    time_added: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_persistence_document(self) -> dict[str, Any]:
        """Return the canonical MongoDB representation of a sample.

        Sample documents use a stable shape. Nullable metadata therefore remains
        present as ``None``; omitting it would make "not recorded" indistinguishable
        from an older document that predates the field.
        """
        return self.model_dump(by_alias=True, exclude_none=False)

    @model_validator(mode="before")
    @classmethod
    def _reject_retired_version_fields(cls, value: Any) -> Any:
        """Reject retired sample fields rather than silently accepting two shapes."""
        if not isinstance(value, dict):
            return value
        retired_keys = {
            "assay",
            "profile",
            "subpanel",
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
                + ". Use asp_id, subpanel_id, environment, platform, and database_versions."
            )
        return value

    @field_validator("sequencing_scope", "omics_layer", mode="before")
    @classmethod
    def _normalize_lowercase(cls, value: Any) -> Any:
        """Trim and lowercase sequencing scope or omics-layer strings.

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

    @field_validator("asp_id", "subpanel_id", mode="before")
    @classmethod
    def _normalize_assay_identifiers(cls, value: Any) -> Any:
        """Canonicalize nonnull assay and subpanel identifiers.

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

    @field_validator("sequencing_scope", mode="before")
    @classmethod
    def _normalize_sequencing_scope(cls, value: Any) -> str:
        """Validate the sample's sequencing scope.

        Args:
            value: Scope label before whitespace and case normalization.

        Returns:
            The canonical configured scope.

        Raises:
            ValueError: If the scope is blank or unsupported.
        """
        return normalize_sequencing_scope(value)

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
    def _validate_case_control_consistency(self) -> "SamplesDoc":
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
    def _derive_platform_capabilities(self) -> "SamplesDoc":
        """Validate read mode and set technology from the platform vocabulary.

        Returns:
            This sample with derived read_technology.

        Raises:
            ValueError: If read mode is incompatible or an explicitly supplied technology
                conflicts with the platform-derived value.
        """
        validate_platform_read_mode(self.platform, self.read_mode)
        derived = derived_read_technology(self.platform)
        if self.read_technology and self.read_technology != derived:
            raise ValueError(
                "read_technology is derived from platform and cannot be set independently"
            )
        self.read_technology = derived
        return self

    @model_validator(mode="after")
    def _validate_omics_payload_consistency(self) -> "SamplesDoc":
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

        if self.omics_layer == "dna":
            if has_rna:
                raise ValueError(
                    "DNA sample must not include RNA file keys "
                    "(fusion_files/expression_path/classification_path/qc)"
                )
            if not has_dna:
                raise ValueError("DNA sample must include at least one DNA data file key")
        elif self.omics_layer == "rna":
            if has_dna:
                raise ValueError(
                    "RNA sample must not include DNA file keys "
                    "(vcf_files/cnv/cov/biomarkers/transloc)"
                )
            if not has_rna:
                raise ValueError("RNA sample must include at least one RNA data file key")
        return self

    @model_validator(mode="before")
    @classmethod
    def _normalize_sample_shape(cls, data: Any) -> Any:
        """Collect file metadata, discard embedded history, and normalize filter profiles.

        Args:
            data: Raw sample dictionary; other inputs pass through.

        Returns:
            A shallow copy with top-level source paths moved into files, uploaded
            checksums applied when absent, and embedded comments/report fields removed.
            Missing reported is derived from latest_report_id.

        Raises:
            ValueError: If supplied filters violate the canonical intent-aware contract.

        Notes:
            Existing nested file dictionaries can receive checksum entries in place.
        """
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        files = dict(normalized.get("files") or {})
        for key in SAMPLE_SOURCE_PATH_KEYS:
            value = normalized.pop(key, None)
            if value:
                files[key] = value if isinstance(value, dict) else {"path": value}
        uploaded_checksums = normalized.get("uploaded_file_checksums") or {}
        if isinstance(uploaded_checksums, dict):
            for key, checksum in uploaded_checksums.items():
                if key in files and isinstance(files[key], dict):
                    files[key].setdefault("checksum", checksum)
        normalized["files"] = files
        normalized.pop("uploaded_file_checksums", None)

        normalized.pop("comments", None)
        normalized.pop("reports", None)
        normalized.pop("report_num", None)
        if "reported" not in normalized:
            normalized["reported"] = bool(normalized.get("latest_report_id"))

        if normalized.get("filters") is not None:
            normalized["filters"] = normalize_sample_filters(
                normalized.get("filters"),
                omics_layer=str(normalized.get("omics_layer") or "dna"),
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
        if self.omics_layer == "rna" and "germline" in self.analysis_intents:
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
