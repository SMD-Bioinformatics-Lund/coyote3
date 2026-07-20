"""Sample document contracts and RNA/DNA consistency rules."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from api.config.constants import (
    ALL_SAMPLE_FILE_KEYS,
    SAMPLE_DATABASE_VERSION_KEY_ALIASES,
    SAMPLE_FILE_KEYS,
    normalize_environment,
    normalize_platform,
    normalize_sequencing_scope,
)
from api.contracts.schemas.base import _DocBase, _StrictDocBase
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
    assay: str | None = None
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


class SampleDnaSnvFiltersDoc(_StrictDocBase):
    max_freq: float = Field(default=1.00, ge=0.0, le=1.0)
    min_freq: float = Field(default=0.0, ge=0.0, le=1.0)
    max_control_freq: float = Field(default=0.05, ge=0.0, le=0.5)
    max_popfreq: float = Field(default=0.05, ge=0.0, le=0.5)
    min_depth: int = Field(default=100, ge=0)
    min_alt_reads: int = Field(default=5, ge=0)
    vep_consequences: list[str] = Field(default_factory=list)
    snvlists: list[str] = Field(default_factory=list)
    adhoc_genes: dict[str, Any] = Field(default_factory=dict)


class SampleDnaCnvFiltersDoc(_StrictDocBase):
    min_cnv_size: int = Field(default=100, ge=0)
    max_cnv_size: int = Field(default=50_000_000, ge=0)
    cnv_loss_cutoff: float = Field(default=-0.3)
    cnv_gain_cutoff: float = Field(default=0.3)
    cnveffects: list[str] = Field(default_factory=lambda: ["gain", "loss"])
    cnvlists: list[str] = Field(default_factory=list)
    adhoc_genes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_consistency(self) -> "SampleDnaCnvFiltersDoc":
        if self.min_cnv_size > self.max_cnv_size:
            raise ValueError("min_cnv_size must be less than or equal to max_cnv_size")
        if self.cnv_loss_cutoff >= self.cnv_gain_cutoff:
            raise ValueError("cnv_loss_cutoff must be less than cnv_gain_cutoff")
        return self


class SampleCoverageFiltersDoc(_StrictDocBase):
    warn_cov: int = Field(default=100, ge=0)
    error_cov: int = Field(default=10, ge=0)

    @model_validator(mode="after")
    def _validate_consistency(self) -> "SampleCoverageFiltersDoc":
        if self.error_cov > self.warn_cov:
            raise ValueError("error_cov must be less than or equal to warn_cov")
        return self


class SampleDnaFiltersDoc(_StrictDocBase):
    snv: SampleDnaSnvFiltersDoc = Field(default_factory=SampleDnaSnvFiltersDoc)
    cnv: SampleDnaCnvFiltersDoc = Field(default_factory=SampleDnaCnvFiltersDoc)
    coverage: SampleCoverageFiltersDoc = Field(default_factory=SampleCoverageFiltersDoc)


class SampleRnaFusionFiltersDoc(_StrictDocBase):
    fusion_callers: list[str] = Field(default_factory=list)
    fusion_effects: list[str] = Field(default_factory=list)
    fusionlists: list[str] = Field(default_factory=list)
    min_spanning_pairs: int = 0
    min_spanning_reads: int = 0
    adhoc_genes: dict[str, Any] = Field(default_factory=dict)


class SampleRnaFiltersDoc(_StrictDocBase):
    fusion: SampleRnaFusionFiltersDoc = Field(default_factory=SampleRnaFusionFiltersDoc)


class SamplesDoc(_DocBase):
    name: str
    assay: str
    subpanel_id: str | None = None
    profile: str
    current_aspc_id: Any | None = None
    current_aspc_key: str | None = None
    current_aspc_version: int | None = None
    genome_build: int | None = None
    vep_version: str | None = None
    database_versions: dict[str, str] = Field(default_factory=dict)
    case_id: str
    control_id: str | None = None
    sample_no: int
    paired: bool | None = False
    sequencing_scope: str
    omics_layer: Literal["dna", "rna"]
    sequencing_technology: str | None = None
    pipeline: str
    pipeline_version: str
    files: dict[str, SampleFileDoc] = Field(default_factory=dict)
    filters: SampleDnaFiltersDoc | SampleRnaFiltersDoc | None = None
    case: SampleCaseControlDoc = Field(default_factory=SampleCaseControlDoc)
    control: SampleCaseControlDoc | None = None
    reported: bool = False
    latest_report_id: Any | None = None
    latest_report_on: datetime | None = None
    time_added: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("sequencing_scope", "omics_layer", mode="before")
    @classmethod
    def _normalize_lowercase(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("assay", "subpanel_id", mode="before")
    @classmethod
    def _normalize_assay_identifiers(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("profile", mode="before")
    @classmethod
    def _normalize_profile(cls, value: Any) -> Any:
        if value is None:
            return None
        return normalize_environment(value, label="profile")

    @field_validator("sequencing_scope", mode="before")
    @classmethod
    def _normalize_sequencing_scope(cls, value: Any) -> str:
        return normalize_sequencing_scope(value)

    @field_validator("sequencing_technology", mode="before")
    @classmethod
    def _normalize_sequencing_technology(cls, value: Any) -> str | None:
        return normalize_platform(value)

    @field_validator("vep_version", mode="before")
    @classmethod
    def _normalize_vep_version(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return str(int(value))
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return str(value).strip() or None

    @field_validator("database_versions", mode="before")
    @classmethod
    def _normalize_database_versions(cls, value: Any) -> dict[str, str]:
        if not isinstance(value, dict):
            return {}
        normalized: dict[str, str] = {}
        for key, raw_value in value.items():
            lookup_key = str(key or "").strip().lower().replace("-", "_").replace(" ", "_")
            lookup_key = lookup_key.replace(".", "_")
            clean_key = SAMPLE_DATABASE_VERSION_KEY_ALIASES.get(lookup_key)
            if not clean_key or raw_value is None:
                continue
            clean_value = str(raw_value).strip()
            if clean_key == "vep":
                clean_value = clean_value.lstrip("vV")
            if clean_value:
                normalized[clean_key] = clean_value
        return normalized

    @field_validator(
        "case_id", "control_id", "name", "assay", "pipeline", "pipeline_version", mode="before"
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
        if "subpanel_id" not in normalized and "subpanel" in normalized:
            normalized["subpanel_id"] = normalized.pop("subpanel")

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
            )
        return normalized
