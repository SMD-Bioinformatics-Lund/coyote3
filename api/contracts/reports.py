"""Report API contracts."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ReportSampleMeta(BaseModel):
    """Provide the report sample meta type."""

    id: str
    name: str | None = None
    assay: str | None = None
    profile: str | None = None


class ReportPreviewMeta(BaseModel):
    """Provide the report preview meta type."""

    request_path: str
    include_snapshot: bool
    snapshot_count: int
    template_status: dict[str, Any]


class ReportPreviewBody(BaseModel):
    """Provide the report preview body type."""

    template: str
    context: dict[str, Any]
    html: str
    snapshot_rows: list[Any]


class ReportPreviewPayload(BaseModel):
    """Represent the report preview payload."""

    sample: ReportSampleMeta
    meta: ReportPreviewMeta
    report: ReportPreviewBody


class ReportSaveBody(BaseModel):
    """Provide the report save body type."""

    id: str
    oid: str
    file: str
    pdf_file: str | None = None
    snapshot_count: int


class ReportSaveMeta(BaseModel):
    """Provide the report save meta type."""

    status: str


class ReportSavePayload(BaseModel):
    """Represent the report save payload."""

    sample: ReportSampleMeta
    report: ReportSaveBody
    meta: ReportSaveMeta


class ReportLibraryItem(BaseModel):
    """Represent one saved report in the report library."""

    oid: str
    report_id: str
    report_name: str | None = None
    sample_id: str
    asp_id: str | None = None
    subpanel_id: str | None = None
    environment: str | None = None
    author: str | None = None
    time_created: datetime | None = None
    finding_count: int = 0
    analysis_counts: dict[str, int] = Field(default_factory=dict)
    has_pdf: bool = False


class ReportLibraryPayload(BaseModel):
    """Represent a paginated, access-scoped report library."""

    reports: list[ReportLibraryItem]
    total: int
    page: int
    per_page: int
    has_next: bool
