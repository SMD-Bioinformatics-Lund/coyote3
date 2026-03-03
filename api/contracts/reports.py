"""Report API contracts."""

from pydantic import BaseModel
from typing import Any


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
