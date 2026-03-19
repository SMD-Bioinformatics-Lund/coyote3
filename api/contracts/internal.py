"""Internal API route contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class RoleLevelsPayload(BaseModel):
    """Represent the role levels payload."""

    status: str
    role_levels: dict[str, int]


class IsglMetaPayload(BaseModel):
    """Represent the isgl meta payload."""

    status: str
    isgl_id: str
    is_adhoc: bool
    display_name: str | None = None


class InternalIngestDependentsRequest(BaseModel):
    """Represent internal dependent-data ingest request payload."""

    sample_id: str
    sample_name: str
    delete_existing: bool = False
    preload: dict[str, Any]


class InternalIngestDependentsPayload(BaseModel):
    """Represent internal dependent-data ingest response payload."""

    status: str
    sample_id: str
    written: dict[str, int]


class InternalSampleIngestSpec(BaseModel):
    """Represent structured fields for sample-bundle ingestion."""

    model_config = ConfigDict(extra="allow")

    name: str
    genome_build: int | None = None
    assay: str | None = None
    profile: str | None = None
    subpanel: str | None = None
    vcf_files: str | None = None
    cnv: str | None = None
    biomarkers: str | None = None
    transloc: str | None = None
    lowcov: str | None = None
    cov: str | None = None
    fusion_files: str | None = None
    expression_path: str | None = None
    classification_path: str | None = None
    qc: str | None = None
    increment: bool = False


class InternalIngestSampleBundleRequest(BaseModel):
    """Represent internal sample+analysis bundle ingest request payload."""

    spec: InternalSampleIngestSpec | None = None
    yaml_content: str | None = None
    update_existing: bool = False


class InternalIngestSampleBundlePayload(BaseModel):
    """Represent internal sample+analysis bundle ingest response payload."""

    status: str
    sample_id: str
    sample_name: str
    written: dict[str, int]
    data_counts: dict[str, int | bool]
