"""Application-control document contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator

from coyote3.config.factory_defaults import factory_value
from coyote3.contracts.schemas.base import _StrictCollectionDocBase


class CeleryControlDoc(BaseModel):
    """Runtime switches for background task families."""

    enabled: bool = factory_value("controls.CeleryControlDoc.enabled")
    sample_ingest_enabled: bool = factory_value("controls.CeleryControlDoc.sample_ingest_enabled")
    collection_writes_enabled: bool = factory_value(
        "controls.CeleryControlDoc.collection_writes_enabled"
    )
    maintenance_enabled: bool = factory_value("controls.CeleryControlDoc.maintenance_enabled")


class RetentionControlDoc(BaseModel):
    """Retention policy values controlled from the admin UI."""

    audit_events_days: int = Field(
        default=factory_value("controls.RetentionControlDoc.audit_events_days"),
        ge=30,
        le=3650,
    )
    notification_days: int = Field(
        default=factory_value("controls.RetentionControlDoc.notification_days"),
        ge=7,
        le=3650,
    )
    disk_log_days: int = Field(
        default=factory_value("controls.RetentionControlDoc.disk_log_days"),
        ge=1,
        le=3650,
    )
    gzip_disk_logs_after_days: int = Field(
        default=factory_value("controls.RetentionControlDoc.gzip_disk_logs_after_days"),
        ge=1,
        le=3650,
    )

    @field_validator("gzip_disk_logs_after_days")
    @classmethod
    def _gzip_before_delete(cls, value: int, info: Any) -> int:
        """Check that log compression is scheduled no later than deletion.

        Args:
            value: Log age in days at which compression starts.
            info: Pydantic context containing the previously validated disk_log_days.

        Returns:
            The compression age unchanged.

        Raises:
            ValueError: If the compression age exceeds the available deletion age.
        """
        disk_log_days = (info.data or {}).get("disk_log_days")
        if disk_log_days is not None and int(value) > int(disk_log_days):
            raise ValueError("gzip_disk_logs_after_days cannot exceed disk_log_days")
        return value


class ModuleControlDoc(BaseModel):
    """Runtime visibility switches for major application modules."""

    dna_analysis_enabled: bool = factory_value("controls.ModuleControlDoc.dna_analysis_enabled")
    rna_analysis_enabled: bool = factory_value("controls.ModuleControlDoc.rna_analysis_enabled")
    reports_enabled: bool = factory_value("controls.ModuleControlDoc.reports_enabled")
    variant_search_enabled: bool = factory_value("controls.ModuleControlDoc.variant_search_enabled")
    knowledgebases_enabled: bool = factory_value("controls.ModuleControlDoc.knowledgebases_enabled")
    ingest_workspace_enabled: bool = factory_value(
        "controls.ModuleControlDoc.ingest_workspace_enabled"
    )
    assay_catalog_enabled: bool = factory_value("controls.ModuleControlDoc.assay_catalog_enabled")


class TieringControlDoc(BaseModel):
    """Runtime availability of tier mutations by finding resource."""

    small_variant_enabled: bool = factory_value("controls.TieringControlDoc.small_variant_enabled")
    cnv_enabled: bool = factory_value("controls.TieringControlDoc.cnv_enabled")
    fusion_enabled: bool = factory_value("controls.TieringControlDoc.fusion_enabled")
    translocation_enabled: bool = factory_value("controls.TieringControlDoc.translocation_enabled")


class CurationControlDoc(BaseModel):
    """Runtime controls for clinical curation actions."""

    tiering: TieringControlDoc = Field(default_factory=TieringControlDoc)


class EmailControlDoc(BaseModel):
    """Runtime switch for all outgoing application email."""

    enabled: bool = factory_value("controls.EmailControlDoc.enabled")


class AppControlsDoc(_StrictCollectionDocBase):
    """Single active runtime-control document stored in MongoDB."""

    control_id: str = factory_value("contracts.app_controls_id")
    email: EmailControlDoc = Field(default_factory=EmailControlDoc)
    celery: CeleryControlDoc = Field(default_factory=CeleryControlDoc)
    retention: RetentionControlDoc = Field(default_factory=RetentionControlDoc)
    modules: ModuleControlDoc = Field(default_factory=ModuleControlDoc)
    curation: CurationControlDoc = Field(default_factory=CurationControlDoc)
    created_on: datetime | None = None
    updated_by: str | None = None
    updated_on: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
