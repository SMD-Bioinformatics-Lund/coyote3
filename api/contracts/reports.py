"""Report API contracts."""

from typing import Any

from pydantic import BaseModel


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


class ReportPreviewBody(BaseModel):
    """Provide the report preview body type."""

    template: str
    context: dict[str, Any]
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
    snapshot_count: int


class ReportSaveMeta(BaseModel):
    """Provide the report save meta type."""

    status: str


class ReportSavePayload(BaseModel):
    """Represent the report save payload."""

    sample: ReportSampleMeta
    report: ReportSaveBody
    meta: ReportSaveMeta
