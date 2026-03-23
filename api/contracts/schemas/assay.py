"""Assay configuration and relationship contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import Field, computed_field, field_validator, model_validator

from api.contracts.schemas.base import VersionHistoryEntryDoc, _DocBase, _StrictDocBase
from api.contracts.schemas.dna import DnaFiltersDoc
from api.contracts.schemas.rna import RnaFiltersDoc


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


class AspConfigDoc(_StrictDocBase):
    aspc_id: str
    assay_name: str
    environment: Literal["production", "development", "testing", "validation"]
    asp_group: str
    asp_category: Literal["dna", "rna"]
    analysis_types: list[str] = Field(default_factory=list)
    is_active: bool = True
    display_name: str
    description: str | None = None
    reference_genome: str | None = None
    platform: str | None = None
    verification_samples: dict[str, list[int]] = Field(default_factory=dict)
    use_diagnosis_genelist: bool = False

    filters: DnaFiltersDoc | RnaFiltersDoc
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
        key = str(value).strip().lower()
        if key not in aliases:
            raise ValueError("environment must be in: production, development, testing, validation")
        return aliases[key]

    @field_validator("aspc_id")
    @classmethod
    def _validate_aspc_id(cls, value: str) -> str:
        if ":" not in value:
            raise ValueError("aspc_id must use assay:environment format")
        return value

    @field_validator("assay_name")
    @classmethod
    def _validate_assay_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("assay_name must be non-empty")
        return value.strip()

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


class AssaySpecificPanelsDoc(_StrictDocBase):
    asp_id: str
    assay_name: str
    asp_group: str
    asp_family: Literal["panel-dna", "panel-rna", "wgs", "wts"]
    asp_category: Literal["dna", "rna"]
    display_name: str
    description: str | None = None
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
        default_factory=lambda: ["small_variants_genelist", "cnv_genelist", "fusion_genelist"]
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
        return value

    @computed_field
    @property
    def gene_count(self) -> int:
        return len(self.genes)


class BlacklistDoc(_StrictDocBase):
    pos: str
    assay_group: str | None = None
    in_normal_perc: float | None = None
