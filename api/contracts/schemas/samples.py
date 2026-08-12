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
    id: str | None = None
    clarity_id: str | None = None
    clarity_pool_id: str | None = None
    ffpe: bool = False
    sequencing_run: str | None = None
    reads: int | None = None
    purity: float | None = None


class SampleFileDoc(_StrictDocBase):
    path: str
    checksum: str | None = None
    size_bytes: int | None = None
    registered_on: datetime | None = None

    @field_validator("path", "checksum", mode="before")
    @classmethod
    def _strip_optional_strings(cls, value: Any) -> Any:
        if value is None:
            return None
        value = str(value).strip()
        return value or None


class SampleCommentRecordDoc(_DocBase):
    sample_oid: Any
    sample_name: str | None = None
    author: str
    text: str
    hidden: int | bool = 0
    hidden_by: str | None = None
    time_created: datetime | None = None
    time_hidden: datetime | None = None


class SampleReportRecordDoc(_DocBase):
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
        return normalize_clinical_identifier(value, label="subpanel_id")


# Public aliases retain the useful domain names for consumers of this contract.
SampleDnaSnvFiltersDoc = SnvFiltersDoc
SampleDnaCnvFiltersDoc = CnvFiltersDoc
SampleCoverageFiltersDoc = CoverageFiltersDoc
SampleRnaFusionFiltersDoc = FusionFiltersDoc
SampleDnaFiltersDoc = DnaFilterProfilesDoc
SampleRnaFiltersDoc = RnaFilterProfilesDoc


class SamplesDoc(_DocBase):
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
    platform: str | None = None
    read_mode: str | None = None
    read_technology: str | None = None
    pipeline: str
    pipeline_version: str
    files: dict[str, SampleFileDoc] = Field(default_factory=dict)
    analysis_intents: list[str] = Field(default_factory=lambda: ["somatic"])
    filters: SampleDnaFiltersDoc | SampleRnaFiltersDoc | None = None
    case: SampleCaseControlDoc = Field(default_factory=SampleCaseControlDoc)
    control: SampleCaseControlDoc | None = None
    reported: bool = False
    latest_report_id: Any | None = None
    latest_report_on: datetime | None = None
    time_added: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("asp_id", "subpanel_id", mode="before")
    @classmethod
    def _normalize_assay_identifiers(cls, value: Any) -> Any:
        if value is None:
            return None
        return normalize_clinical_identifier(value, label="clinical scope identifier")

    @field_validator("environment", mode="before")
    @classmethod
    def _normalize_profile(cls, value: Any) -> Any:
        if value is None:
            return None
        return normalize_environment(value, label="environment")

    @field_validator("sequencing_scope", mode="before")
    @classmethod
    def _normalize_sequencing_scope(cls, value: Any) -> str:
        return normalize_sequencing_scope(value)

    @field_validator("platform", mode="before")
    @classmethod
    def _normalize_platform(cls, value: Any) -> str | None:
        return normalize_platform(value)

    @field_validator("read_mode", mode="before")
    @classmethod
    def _normalize_read_mode(cls, value: Any) -> str | None:
        return normalize_read_mode(value)

    @field_validator("database_versions", mode="before")
    @classmethod
    def _normalize_database_versions(cls, value: Any) -> dict[str, str]:
        return normalize_database_versions(value)

    @field_validator("analysis_intents", mode="before")
    @classmethod
    def _normalize_analysis_intents(cls, value: Any) -> list[str]:
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

    @field_validator(
        "case_id", "control_id", "name", "asp_id", "pipeline", "pipeline_version", mode="before"
    )
    @classmethod
    def _strip_strings(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @model_validator(mode="after")
    def _validate_case_control_consistency(self) -> "SamplesDoc":
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
