"""Report API contracts."""

from typing import Any

from pydantic import BaseModel


class ReportSampleMeta(BaseModel):
    id: str
    name: str | None = None
    assay: str | None = None
    profile: str | None = None


class ReportPreviewMeta(BaseModel):
    request_path: str
    include_snapshot: bool
    snapshot_count: int


class ReportPreviewBody(BaseModel):
    template: str
    context: dict[str, Any]
    snapshot_rows: list[Any]


class ReportPreviewPayload(BaseModel):
    sample: ReportSampleMeta
    meta: ReportPreviewMeta
    report: ReportPreviewBody


class ReportSaveBody(BaseModel):
    id: str
    oid: str
    file: str
    snapshot_count: int


class ReportSaveMeta(BaseModel):
    status: str


class ReportSavePayload(BaseModel):
    sample: ReportSampleMeta
    report: ReportSaveBody
    meta: ReportSaveMeta
