"""Permitted resource metadata snapshots shared by HTTP responses and Python clients."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ResourceMetadata(BaseModel):
    """Represent read-only permitted metadata, preserving absent optional values as null."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class SampleMetadata(ResourceMetadata):
    """Nonclinical sample identity, assay context and ingestion state."""

    name: str | None = None
    asp_id: str | None = None
    asp_group: str | None = None
    diagnosis_id: str | None = None
    environment: str | None = None
    asp_category: str | None = None
    asp_family: str | None = None
    ingest_status: str | None = None
    reported: bool | None = None
    version: int | None = None
    time_added: datetime | None = None


class AssayMetadata(ResourceMetadata):
    """Active assay identity, availability and supported analyses and files."""

    asp_id: str | None = None
    display_name: str | None = None
    asp_group: str | None = None
    asp_category: str | None = None
    asp_family: str | None = None
    platform: str | None = None
    is_active: bool | None = None
    version: int | None = None
    supported_analyses: list[str] | None = None
    expected_files: list[str] | None = None
    required_files: list[str] | None = None


class ConfigurationMetadata(ResourceMetadata):
    """Active configuration identity, analysis types and report section names."""

    aspc_id: str | None = None
    display_name: str | None = None
    asp_id: str | None = None
    asp_group: str | None = None
    diagnosis_id: str | None = None
    environment: str | None = None
    asp_category: str | None = None
    platform: str | None = None
    reference_genome: str | None = None
    is_active: bool | None = None
    version: int | None = None
    analysis_types: list[str] | None = None
    report_sections: list[str] | None = None


class GroupMetadata(ResourceMetadata):
    """Biological group identity, hierarchy and availability."""

    group_id: str | None = None
    display_name: str | None = None
    parent_group_id: str | None = None
    is_active: bool | None = None
    version: int | None = None


class DiagnosisMetadata(ResourceMetadata):
    """Shared diagnosis identity, description and linked assays."""

    diagnosis_id: str | None = None
    display_name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    version: int | None = None
    asp_ids: list[str] | None = None


class GeneListMetadata(ResourceMetadata):
    """Gene-list metadata and entry count, excluding gene content."""

    isgl_id: str | None = None
    displayname: str | None = None
    name: str | None = None
    list_type: list[str] | None = None
    diagnosis: list[str] | None = None
    asp_ids: list[str] | None = None
    asp_groups: list[str] | None = None
    gene_count: int | None = None
    is_active: bool | None = None
    is_public: bool | None = None
    adhoc: bool | None = None
    version: int | None = None
