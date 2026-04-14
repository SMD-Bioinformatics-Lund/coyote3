"""Assay configuration and relationship contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from api.contracts.schemas.base import VersionHistoryEntryDoc, _DocBase, _StrictDocBase
from api.contracts.schemas.dna import DnaFiltersDoc
from api.contracts.schemas.rna import RnaFiltersDoc
from shared.config_constants import (
    ALL_SAMPLE_FILE_KEYS,
    DNA_ANALYSIS_TYPE_OPTIONS,
    RNA_ANALYSIS_TYPE_OPTIONS,
    SAMPLE_FILE_KEYS,
    expected_file_keys,
    normalize_asp_category,
    normalize_asp_family,
    normalize_asp_group,
    normalize_environment,
    normalize_platform,
    validate_identifier,
)

DNA_EXPECTED_FILE_OPTIONS: tuple[str, ...] = SAMPLE_FILE_KEYS["dna"]
RNA_EXPECTED_FILE_OPTIONS: tuple[str, ...] = SAMPLE_FILE_KEYS["rna"]
ALL_EXPECTED_FILE_OPTIONS: tuple[str, ...] = ALL_SAMPLE_FILE_KEYS


def _normalize_analysis_option(value: Any) -> str:
    raw = str(value or "").strip().upper().replace(" ", "_")
    aliases = {
        "BIOMARKERS": "BIOMARKER",
        "CNVPROFILE": "CNV_PROFILE",
        "CNV_PROFILE": "CNV_PROFILE",
        "CNV-PROFILE": "CNV_PROFILE",
        "CNV__PROFILE": "CNV_PROFILE",
    }
    return aliases.get(raw, raw)


class AssayPanelToAssayGroupMappingDoc(_DocBase):
    """One on One relationship between assay panel and assay group."""

    asp: str
    asp_group: str


class AspcReportingDoc(_StrictDocBase):
    # Reporting
    report_sections: list[str] = Field(default_factory=list)
    report_header: str
    report_method: str
    report_description: str
    general_report_summary: str
    plots_path: str
    report_folder: str

    @model_validator(mode="after")
    def _validate_paths(self) -> AspcReportingDoc:
        # Basic sanity checks (not OS-dependent strict validation)
        if not self.plots_path:
            raise ValueError("plots_path cannot be empty")

        if not self.report_folder:
            raise ValueError("report_folder cannot be empty")

        if not self.report_header:
            raise ValueError("report_header cannot be empty")

        if not self.report_method:
            raise ValueError("report_method cannot be empty")

        if not self.report_description:
            raise ValueError("report_description cannot be empty")

        if not self.general_report_summary:
            raise ValueError("general_report_summary cannot be empty")

        return self

    @field_validator("report_sections", mode="before")
    @classmethod
    def _normalize_report_sections(cls, value: Any) -> list[str]:
        if value is None:
            return []
        values = value if isinstance(value, list) else [value]
        normalized = [
            _normalize_analysis_option(item) for item in values if str(item or "").strip()
        ]
        return list(dict.fromkeys(normalized))


class AspcQueryDoc(BaseModel):
    """ASPC query override buckets by domain."""

    model_config = ConfigDict(extra="forbid")

    snv: dict[str, Any] = Field(default_factory=dict)
    cnv: dict[str, Any] = Field(default_factory=dict)
    fusion: dict[str, Any] = Field(default_factory=dict)
    transloc: dict[str, Any] = Field(default_factory=dict)


class AspConfigDoc(_StrictDocBase):
    aspc_id: str
    assay_name: str
    environment: str
    asp_group: str
    asp_category: str
    analysis_types: list[str] = Field(default_factory=list)
    is_active: bool = True
    display_name: str
    description: str | None = None
    reference_genome: str | None = None
    platform: str | None = None
    verification_samples: dict[str, list[int]] = Field(default_factory=dict)
    use_diagnosis_genelist: bool = False

    filters: DnaFiltersDoc | RnaFiltersDoc
    query: AspcQueryDoc = Field(default_factory=AspcQueryDoc)
    reporting: AspcReportingDoc

    # Versioning
    version: int = 1
    created_by: str | None = None
    created_on: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: str | None = None
    updated_on: datetime | None = None
    version_history: list[VersionHistoryEntryDoc] = Field(default_factory=list)

    @field_validator("environment", mode="before")
    @classmethod
    def _normalize_environment(cls, value: Any) -> str:
        return normalize_environment(value)

    @field_validator("asp_category", mode="before")
    @classmethod
    def _normalize_asp_category(cls, value: Any) -> str:
        return normalize_asp_category(value)

    @field_validator("platform", mode="before")
    @classmethod
    def _normalize_platform(cls, value: Any) -> str | None:
        return normalize_platform(value)

    @field_validator("aspc_id")
    @classmethod
    def _validate_aspc_id(cls, value: str) -> str:
        if ":" not in value:
            raise ValueError("aspc_id must use assay:environment format")
        return value

    @field_validator("assay_name", mode="before")
    @classmethod
    def _validate_assay_name(cls, value: Any) -> str:
        return validate_identifier(value, label="assay_name")

    @field_validator("asp_group", mode="before")
    @classmethod
    def _normalize_asp_group(cls, value: Any) -> str:
        return normalize_asp_group(value)

    @model_validator(mode="after")
    def _validate_aspc_match(self) -> "AspConfigDoc":
        assay, environment = self.aspc_id.split(":", 1)
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
        if assay != self.assay_name:
            raise ValueError("aspc_id assay segment must match assay_name")
        if (
            aliases.get(environment.strip().lower(), environment.strip().lower())
            != self.environment
        ):
            raise ValueError("aspc_id environment segment must match environment")

        if self.asp_category == "dna" and not isinstance(self.filters, DnaFiltersDoc):
            raise ValueError("filters must be AspcDnaFiltersDoc when asp_category='dna'")

        if self.asp_category == "rna" and not isinstance(self.filters, RnaFiltersDoc):
            raise ValueError("filters must be AspcRnaFiltersDoc when asp_category='rna'")

        return self

    @field_validator("analysis_types", mode="before")
    @classmethod
    def _normalize_analysis_types(cls, value: Any) -> list[str]:
        if value is None:
            return []
        values = value if isinstance(value, list) else [value]
        normalized = [
            _normalize_analysis_option(item) for item in values if str(item or "").strip()
        ]
        return list(dict.fromkeys(normalized))

    @model_validator(mode="after")
    def _validate_analysis_and_reporting_options(self) -> "AspConfigDoc":
        allowed_analysis = (
            set(DNA_ANALYSIS_TYPE_OPTIONS)
            if self.asp_category == "dna"
            else set(RNA_ANALYSIS_TYPE_OPTIONS)
        )
        invalid_analysis = [value for value in self.analysis_types if value not in allowed_analysis]
        if invalid_analysis:
            raise ValueError(
                f"analysis_types contains invalid values: {invalid_analysis}. "
                f"Allowed values are: {sorted(allowed_analysis)}"
            )

        invalid_report_sections = [
            value for value in self.reporting.report_sections if value not in allowed_analysis
        ]
        if invalid_report_sections:
            raise ValueError(
                f"report_sections contains invalid values: {invalid_report_sections}. "
                f"Allowed values are: {sorted(allowed_analysis)}"
            )
        return self


class AssaySpecificPanelsDoc(_StrictDocBase):
    asp_id: str
    assay_name: str
    asp_group: str
    asp_family: str
    asp_category: str
    display_name: str
    description: str | None = None
    expected_files: list[str] = Field(default_factory=list)
    required_files: list[str] = Field(default_factory=list)
    covered_genes: list[str] = Field(default_factory=list)
    germline_genes: list[str] = Field(default_factory=list)
    accredited: bool = False
    kit_name: str | None = None
    kit_type: str | None = None
    kit_version: str | None = None
    platform: str | None = None
    read_mode: str | None = None
    read_length: int | None = None
    capture_method: str | None = None
    target_region_size: int | None = None
    is_active: bool = True
    version: int = 1
    created_by: str | None = None
    created_on: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: str | None = None
    updated_on: datetime | None = None
    version_history: list[VersionHistoryEntryDoc] = Field(default_factory=list)

    @field_validator("asp_id", mode="before")
    @classmethod
    def _validate_asp_id(cls, value: Any) -> str:
        return validate_identifier(value, label="asp_id")

    @field_validator("assay_name", mode="before")
    @classmethod
    def _validate_assay_name(cls, value: Any) -> str:
        return validate_identifier(value, label="assay_name")

    @field_validator("asp_category", mode="before")
    @classmethod
    def _normalize_asp_category(cls, value: Any) -> str:
        return normalize_asp_category(value)

    @field_validator("asp_family", mode="before")
    @classmethod
    def _normalize_asp_family(cls, value: Any) -> str:
        return normalize_asp_family(value)

    @field_validator("asp_group", mode="before")
    @classmethod
    def _normalize_asp_group(cls, value: Any) -> str:
        return normalize_asp_group(value)

    @field_validator("platform", mode="before")
    @classmethod
    def _normalize_platform(cls, value: Any) -> str | None:
        return normalize_platform(value)

    @field_validator("expected_files", mode="before")
    @classmethod
    def _normalize_expected_files(cls, value: Any) -> list[str]:
        if value is None:
            return []
        values = value if isinstance(value, list) else [value]
        normalized: list[str] = []
        for item in values:
            key = str(item or "").strip().lower()
            if key:
                normalized.append(key)
        return list(dict.fromkeys(normalized))

    @field_validator("required_files", mode="before")
    @classmethod
    def _normalize_required_files(cls, value: Any) -> list[str]:
        if value is None:
            return []
        values = value if isinstance(value, list) else [value]
        normalized: list[str] = []
        for item in values:
            key = str(item or "").strip().lower()
            if key:
                normalized.append(key)
        return list(dict.fromkeys(normalized))

    @model_validator(mode="after")
    def _validate_expected_files(self) -> "AssaySpecificPanelsDoc":
        allowed = (
            set(DNA_EXPECTED_FILE_OPTIONS)
            if self.asp_category == "dna"
            else set(RNA_EXPECTED_FILE_OPTIONS)
        )
        if not self.expected_files:
            self.expected_files = list(expected_file_keys(self.asp_category))
        invalid = [value for value in self.expected_files if value not in allowed]
        if invalid:
            raise ValueError(
                f"expected_files contains invalid values: {invalid}. "
                f"Allowed values are: {sorted(allowed)}"
            )
        invalid_required = [value for value in self.required_files if value not in allowed]
        if invalid_required:
            raise ValueError(
                f"required_files contains invalid values: {invalid_required}. "
                f"Allowed values are: {sorted(allowed)}"
            )
        missing_from_expected = [
            value for value in self.required_files if value not in self.expected_files
        ]
        if missing_from_expected:
            raise ValueError(
                "required_files must also be included in expected_files. "
                f"Missing from expected_files: {missing_from_expected}"
            )
        return self

    @property
    @computed_field
    def covered_genes_count(self) -> int:
        return len(self.covered_genes)

    @property
    @computed_field
    def germline_genes_count(self) -> int:
        return len(self.germline_genes)


class InsilicoGenelistsDoc(_StrictDocBase):
    isgl_id: str
    diagnosis: list[str] = Field(default_factory=list)
    name: str
    displayname: str
    list_type: list[str] = Field(
        default_factory=lambda: ["small_variant_genelist", "cnv_genelist", "fusion_genelist"]
    )
    adhoc: bool = False
    is_public: bool = False
    is_active: bool = True
    assay_groups: list[str] = Field(default_factory=list)
    genes: list[str] = Field(default_factory=list)
    assays: list[str] = Field(default_factory=list)
    version: int = 1
    created_by: str | None = None
    created_on: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: str | None = None
    updated_on: datetime | None = None
    version_history: list[VersionHistoryEntryDoc] = Field(default_factory=list)

    @field_validator("diagnosis", mode="before")
    @classmethod
    def _normalize_diagnosis(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            value = [value]
        if not value:
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    @field_validator("assays")
    @classmethod
    def _validate_assays(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("assays must include at least one assay id")
        return value

    @field_validator("assay_groups")
    @classmethod
    def _validate_assay_groups(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("assay_groups must include at least one assay group")
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            group = normalize_asp_group(item)
            if group not in seen:
                normalized.append(group)
                seen.add(group)
        return normalized

    @computed_field
    @property
    def gene_count(self) -> int:
        return len(self.genes)


class BlacklistDoc(_StrictDocBase):
    pos: str
    assay_group: str | None = None
    in_normal_perc: float | None = None
