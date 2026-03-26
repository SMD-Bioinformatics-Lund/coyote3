"""Sample document contracts and RNA/DNA consistency guards."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from api.contracts.schemas.base import _DocBase
from api.contracts.schemas.dna import DnaFiltersDoc
from api.contracts.schemas.rna import RnaFiltersDoc

DNA_SAMPLE_FILE_KEYS: tuple[str, ...] = (
    "vcf_files",
    "cnv",
    "cnvprofile",
    "cov",
    "transloc",
    "biomarkers",
    "lowcov",
)
RNA_SAMPLE_FILE_KEYS: tuple[str, ...] = (
    "fusion_files",
    "expression_path",
    "classification_path",
    "qc",
)
SAMPLE_SOURCE_PATH_KEYS: tuple[str, ...] = DNA_SAMPLE_FILE_KEYS + RNA_SAMPLE_FILE_KEYS


class SampleCaseControlDoc(_DocBase):
    id: str | None = None
    clarity_id: str | None = None
    clarity_pool_id: str | None = None
    ffpe: bool = False
    sequencing_run: str | None = None
    reads: int | None = None
    purity: float | None = None


class SampleCommentDoc(_DocBase):
    author: str
    text: str
    hidden: int | bool | None = None
    hidden_by: str | None = None
    time_created: datetime | None = None
    time_hidden: datetime | None = None


class SampleReportDoc(_DocBase):
    author: str | None = None
    filepath: str | None = None
    report_id: str | None = None
    report_name: str | None = None
    report_num: int | None = None
    report_type: str | None = None
    time_created: datetime | None = None


class SamplesDoc(_DocBase):
    name: str
    assay: str
    subpanel: str | None
    profile: Literal["production", "development", "testing", "validation"]
    genome_build: int | None = None
    case_id: str
    control_id: str | None = None
    sample_no: int
    paired: bool | None = False
    sequencing_scope: Literal["panel", "wgs", "wts"]
    omics_layer: Literal["dna", "rna"]
    sequencing_technology: str | None = None
    pipeline: str
    pipeline_version: str
    vcf_files: str | None = None
    cnv: str | None = None
    cnvprofile: str | None = None
    cov: str | None = None
    transloc: str | None = None
    biomarkers: str | None = None
    fusion_files: str | None = None
    expression_path: str | None = None
    classification_path: str | None = None
    qc: str | None = None
    filters: DnaFiltersDoc | RnaFiltersDoc = Field(default_factory=dict)
    comments: list[SampleCommentDoc] = Field(default_factory=list)
    reports: list[SampleReportDoc] = Field(default_factory=list)
    case: SampleCaseControlDoc = Field(default_factory=dict)
    control: SampleCaseControlDoc | None = None
    report_num: int = 0
    time_added: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("sequencing_scope", "omics_layer", mode="before")
    @classmethod
    def _normalize_lowercase(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("assay", "subpanel", mode="before")
    @classmethod
    def _normalize_assay_identifiers(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("profile", mode="before")
    @classmethod
    def _normalize_profile(cls, value: Any) -> Any:
        if value is None:
            return None
        raw = str(value).strip().lower()
        aliases = {
            "prod": "production",
            "production": "production",
            "dev": "development",
            "development": "development",
            "test": "testing",
            "testing": "testing",
            "validation": "validation",
            "stage": "validation",
            "staging": "validation",
        }
        if raw not in aliases:
            raise ValueError("profile must be one of: production, development, testing, validation")
        return aliases[raw]

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
        dna_fields = tuple(getattr(self, key, None) for key in DNA_SAMPLE_FILE_KEYS)
        rna_fields = tuple(getattr(self, key, None) for key in RNA_SAMPLE_FILE_KEYS)
        has_dna = any(bool(v) for v in dna_fields)
        has_rna = any(bool(v) for v in rna_fields)

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
                    "(vcf_files/cnv/cov/lowcov/biomarkers/transloc)"
                )
            if not has_rna:
                raise ValueError("RNA sample must include at least one RNA data file key")
        return self
