"""Application-control document contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator

from api.contracts.schemas.base import _StrictCollectionDocBase


class CeleryControlDoc(BaseModel):
    """Runtime switches for background task families."""

    enabled: bool = True
    sample_ingest_enabled: bool = True
    collection_writes_enabled: bool = True
    maintenance_enabled: bool = True


class RetentionControlDoc(BaseModel):
    """Retention policy values controlled from the admin UI."""

    audit_events_days: int = Field(default=730, ge=30, le=3650)
    notification_days: int = Field(default=180, ge=7, le=3650)
    disk_log_days: int = Field(default=30, ge=1, le=3650)
    gzip_disk_logs_after_days: int = Field(default=1, ge=1, le=3650)

    @field_validator("gzip_disk_logs_after_days")
    @classmethod
    def _gzip_before_delete(cls, value: int, info: Any) -> int:
        disk_log_days = (info.data or {}).get("disk_log_days")
        if disk_log_days is not None and int(value) > int(disk_log_days):
            raise ValueError("gzip_disk_logs_after_days cannot exceed disk_log_days")
        return value


class ModuleControlDoc(BaseModel):
    """Runtime visibility switches for major application modules."""

    dna_analysis_enabled: bool = True
    rna_analysis_enabled: bool = True
    reports_enabled: bool = True
    variant_search_enabled: bool = True
    knowledgebases_enabled: bool = True
    ingest_workspace_enabled: bool = True
    assay_catalog_enabled: bool = True


class TieringControlDoc(BaseModel):
    """Runtime availability of tier mutations by finding resource."""

    small_variant_enabled: bool = True
    cnv_enabled: bool = False
    fusion_enabled: bool = True
    translocation_enabled: bool = False


class CurationControlDoc(BaseModel):
    """Runtime controls for clinical curation actions."""

    tiering: TieringControlDoc = Field(default_factory=TieringControlDoc)


class AppControlsDoc(_StrictCollectionDocBase):
    """Single active runtime-control document stored in MongoDB."""

    control_id: str = "default"
    celery: CeleryControlDoc = Field(default_factory=CeleryControlDoc)
    retention: RetentionControlDoc = Field(default_factory=RetentionControlDoc)
    modules: ModuleControlDoc = Field(default_factory=ModuleControlDoc)
    curation: CurationControlDoc = Field(default_factory=CurationControlDoc)
    created_on: datetime | None = None
    updated_by: str | None = None
    updated_on: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
