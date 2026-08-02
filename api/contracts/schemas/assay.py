"""Assay configuration and relationship contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import Field, computed_field, field_validator, model_validator

from api.config.constants import (
    ALL_SAMPLE_FILE_KEYS,
    DNA_ANALYSIS_TYPE_OPTIONS,
    GENELIST_ADHOC_TYPE_OPTIONS,
    GENELIST_STANDARD_TYPE_OPTIONS,
    GENELIST_TYPE_OPTIONS,
    RNA_ANALYSIS_TYPE_OPTIONS,
    SAMPLE_FILE_KEYS,
    SUBPANEL_BASE_ID,
    expected_file_keys,
    normalize_analysis_type,
    normalize_asp_category,
    normalize_asp_family,
    normalize_asp_group,
    normalize_clinical_identifier,
    normalize_environment,
    normalize_genelist_type,
    normalize_platform,
    normalize_read_mode,
)
from api.config.sequencing import derived_read_technology, validate_platform_read_mode
from api.contracts.schemas.base import _DocBase, _StrictDocBase
from api.contracts.schemas.filter_profiles import DnaFilterProfilesDoc, RnaFilterProfilesDoc
from api.domain.common.sample_filters import normalize_analysis_intents, normalize_sample_filters

DNA_EXPECTED_FILE_OPTIONS: tuple[str, ...] = SAMPLE_FILE_KEYS["dna"]
RNA_EXPECTED_FILE_OPTIONS: tuple[str, ...] = SAMPLE_FILE_KEYS["rna"]
ALL_EXPECTED_FILE_OPTIONS: tuple[str, ...] = ALL_SAMPLE_FILE_KEYS


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
        normalized = [normalize_analysis_type(item) for item in values if str(item or "").strip()]
        return list(dict.fromkeys(normalized))


class AspcCatalogDoc(_StrictDocBase):
    """Public catalog metadata for one ASPC environment/subpanel tuple."""

    is_public: bool = True
    display_order: int = 100
    title: str | None = None
    description: str | None = None
    input_material: str | None = None
    tat: str | None = None
    sample_modes: list[str] = Field(default_factory=list)
    clinical_indications: list[str] = Field(default_factory=list)
    limitations: str | None = None
    public_notes: str | None = None

    @field_validator("sample_modes", "clinical_indications", mode="before")
    @classmethod
    def _normalize_text_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        values = value if isinstance(value, list) else [value]
        return list(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))


class AspConfigDoc(_StrictDocBase):
    aspc_id: str
    asp_id: str
    subpanel_id: str = SUBPANEL_BASE_ID
    environment: str
    asp_group: str
    asp_category: str
    analysis_types: list[str] = Field(default_factory=list)
    analysis_intents: list[str] = Field(default_factory=lambda: ["somatic"])
    is_active: bool = True
    display_name: str
    description: str | None = None
    reference_genome: str | None = None
    platform: str | None = None
    verification_samples: dict[str, list[int]] = Field(default_factory=dict)
    use_diagnosis_genelist: bool = False

    filters: DnaFilterProfilesDoc | RnaFilterProfilesDoc
    reporting: AspcReportingDoc
    catalog: AspcCatalogDoc = Field(default_factory=AspcCatalogDoc)

    version: int = 1
    created_by: str | None = None
    created_on: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: str | None = None
    updated_on: datetime | None = None

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
        return normalize_clinical_identifier(value, label="aspc_id")

    @field_validator("asp_id", mode="before")
    @classmethod
    def _validate_asp_id(cls, value: Any) -> str:
        return normalize_clinical_identifier(value, label="asp_id")

    @field_validator("subpanel_id", mode="before")
    @classmethod
    def _validate_subpanel_id(cls, value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return SUBPANEL_BASE_ID
        return normalize_clinical_identifier(raw, label="subpanel_id")

    @field_validator("asp_group", mode="before")
    @classmethod
    def _normalize_asp_group(cls, value: Any) -> str:
        return normalize_asp_group(value)

    @model_validator(mode="after")
    def _validate_filter_contract(self) -> "AspConfigDoc":
        if self.asp_category == "dna" and not isinstance(self.filters, DnaFilterProfilesDoc):
            raise ValueError("filters must be DnaFilterProfilesDoc when asp_category='dna'")

        if self.asp_category == "rna" and not isinstance(self.filters, RnaFilterProfilesDoc):
            raise ValueError("filters must be RnaFilterProfilesDoc when asp_category='rna'")

        return self

    @field_validator("analysis_types", mode="before")
    @classmethod
    def _normalize_analysis_types(cls, value: Any) -> list[str]:
        if value is None:
            return []
        values = value if isinstance(value, list) else [value]
        normalized = [normalize_analysis_type(item) for item in values if str(item or "").strip()]
        return list(dict.fromkeys(normalized))

    @field_validator("analysis_intents", mode="before")
    @classmethod
    def _normalize_analysis_intents(cls, value: Any) -> list[str]:
        values = value if isinstance(value, list) else [value]
        return list(
            dict.fromkeys(
                str(item or "").strip().lower() for item in values if str(item or "").strip()
            )
        ) or ["somatic"]

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
        if not self.analysis_types:
            raise ValueError("analysis_types must include at least one enabled analysis")
        self.analysis_intents = normalize_analysis_intents(
            self.analysis_intents, omics_layer=self.asp_category
        )
        if "germline" in self.analysis_intents and "SNV" not in self.analysis_types:
            raise ValueError("germline analysis requires SNV in analysis_types")
        if not self.reporting.report_sections:
            raise ValueError("reporting.report_sections must include at least one report section")
        unavailable_sections = [
            value for value in self.reporting.report_sections if value not in self.analysis_types
        ]
        if unavailable_sections:
            raise ValueError(
                "reporting.report_sections must be enabled in analysis_types: "
                f"{unavailable_sections}"
            )
        filter_profiles = self.filters.model_dump(exclude_none=True)
        normalize_sample_filters(
            filter_profiles,
            omics_layer=self.asp_category,
            analysis_intents=self.analysis_intents,
            canonical=True,
        )
        somatic = filter_profiles.get("somatic") or {}
        required_sections = {"SNV": "snv", "CNV": "cnv", "COVERAGE": "coverage", "FUSION": "fusion"}
        for analysis_type, section in required_sections.items():
            if analysis_type in self.analysis_types and not somatic.get(section):
                raise ValueError(
                    f"analysis_types includes {analysis_type} but filters.somatic.{section} is missing"
                )
        if "germline" in self.analysis_intents:
            if not (filter_profiles.get("germline") or {}).get("snv"):
                raise ValueError("germline analysis requires filters.germline.snv")
        return self


class AssaySpecificPanelsDoc(_StrictDocBase):
    asp_id: str
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
    read_technology: str | None = None
    read_length: int | None = None
    capture_method: str | None = None
    target_region_size: int | None = None
    is_active: bool = True
    version: int = 1
    created_by: str | None = None
    created_on: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: str | None = None
    updated_on: datetime | None = None

    @field_validator("asp_id", mode="before")
    @classmethod
    def _validate_asp_id(cls, value: Any) -> str:
        return normalize_clinical_identifier(value, label="asp_id")

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

    @field_validator("read_mode", mode="before")
    @classmethod
    def _normalize_read_mode(cls, value: Any) -> str | None:
        return normalize_read_mode(value)

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

    @model_validator(mode="after")
    def _derive_platform_capabilities(self) -> "AssaySpecificPanelsDoc":
        validate_platform_read_mode(self.platform, self.read_mode)
        derived = derived_read_technology(self.platform)
        if self.read_technology and self.read_technology != derived:
            raise ValueError(
                "read_technology is derived from platform and cannot be set independently"
            )
        self.read_technology = derived
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
    # TODO: add a dedicated fusion genelist schema once the accepted partner and
    # breakpoint format is defined. SNV/CNV lists stay as one-symbol-per-entry.
    isgl_id: str
    subpanel_id: str = SUBPANEL_BASE_ID
    diagnosis: list[str] = Field(default_factory=list)
    name: str
    displayname: str
    list_type: list[str] = Field(default_factory=lambda: list(GENELIST_TYPE_OPTIONS))
    adhoc: bool = False
    is_public: bool = False
    is_active: bool = True
    asp_groups: list[str] = Field(default_factory=list)
    genes: list[str] = Field(default_factory=list)
    germline_genes: list[str] = Field(default_factory=list)
    asp_ids: list[str] = Field(default_factory=list)
    version: int = 1
    created_by: str | None = None
    created_on: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: str | None = None
    updated_on: datetime | None = None

    @field_validator("isgl_id", mode="before")
    @classmethod
    def _validate_isgl_id(cls, value: Any) -> str:
        return normalize_clinical_identifier(value, label="isgl_id")

    @field_validator("diagnosis", mode="before")
    @classmethod
    def _normalize_diagnosis(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            value = [value]
        if not value:
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    @field_validator("subpanel_id", mode="before")
    @classmethod
    def _validate_subpanel_id(cls, value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return SUBPANEL_BASE_ID
        return normalize_clinical_identifier(raw, label="subpanel_id")

    @field_validator("list_type", mode="before")
    @classmethod
    def _normalize_list_type(cls, value: Any) -> list[str]:
        if value is None:
            return list(GENELIST_TYPE_OPTIONS)
        values = value if isinstance(value, list) else [value]
        normalized = [normalize_genelist_type(item) for item in values if str(item or "").strip()]
        return list(dict.fromkeys(normalized))

    @model_validator(mode="after")
    def _validate_adhoc_list_types(self) -> "InsilicoGenelistsDoc":
        allowed = GENELIST_ADHOC_TYPE_OPTIONS if self.adhoc else GENELIST_STANDARD_TYPE_OPTIONS
        invalid = [value for value in self.list_type if value not in allowed]
        if invalid:
            mode = "adhoc" if self.adhoc else "standard"
            raise ValueError(
                f"{mode} genelists may only use list_type values: {', '.join(allowed)}"
            )
        return self

    @field_validator("asp_ids")
    @classmethod
    def _validate_asp_ids(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("asp_ids must include at least one ASP identifier")
        return [normalize_clinical_identifier(item, label="asp_ids") for item in value]

    @field_validator("asp_groups")
    @classmethod
    def _validate_asp_groups(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("asp_groups must include at least one ASP group")
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

    @computed_field
    @property
    def germline_gene_count(self) -> int:
        return len(self.germline_genes)


class BlacklistDoc(_StrictDocBase):
    pos: str
    assay_group: str | None = None
    in_normal_perc: float | None = None
