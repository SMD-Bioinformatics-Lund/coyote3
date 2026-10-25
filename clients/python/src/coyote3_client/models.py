"""Client response models independent of server wiring and clinical business logic."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue, SerializeAsAny

ItemT = TypeVar("ItemT", bound=BaseModel)
JsonObject = dict[str, JsonValue]


class SdkModel(BaseModel):
    """Validate known response fields while retaining additive server fields."""

    model_config = ConfigDict(extra="allow", frozen=True, strict=True, populate_by_name=True)


class ReportTrial(SdkModel):
    """Matching temporary HTML/PDF output; no report record has been created."""

    html: str
    pdf_base64: str
    filename: str
    snapshot_count: int


class SessionUser(SdkModel):
    """Authenticated identity metadata, excluding reusable session credentials."""

    username: str


class SessionResponse(SdkModel):
    """Validated session user with optional browser-only CSRF metadata."""

    user: SessionUser
    csrf_token: str | None = Field(default=None, repr=False)


class Classification(SdkModel):
    """Server-supplied classification; the SDK does not calculate clinical tiers."""

    class_value: int | None = Field(default=None, alias="class")


class FindingData(SdkModel):
    """A server finding row with typed identity, classification and review flags."""

    id: str = Field(alias="_id")
    classification: Classification | None = None
    fp: str | bool | None = None
    irrelevant: str | bool | None = None
    interesting: str | bool | None = None


class FindingDetail(SdkModel):
    """Finding detail context, preserving annotations and modality-specific fields."""

    sample: JsonObject
    variant: FindingData | None = None
    cnv: FindingData | None = None
    fusion: FindingData | None = None
    translocation: FindingData | None = None


class PageInfo(SdkModel):
    """Server pagination state; continuation is controlled by has_next."""

    page: int = Field(ge=1)
    per_page: int = Field(ge=1)
    has_next: bool
    total: int | None = Field(default=None, ge=0)


class Page(SdkModel, Generic[ItemT]):
    """One typed page with its original API envelope available as payload."""

    items: list[SerializeAsAny[ItemT]]
    pagination: PageInfo
    payload: JsonObject = Field(repr=False)


class ChangeResult(SdkModel):
    """A server-confirmed sample or finding change."""

    sample_id: str
    action: str


class SampleContext(SdkModel):
    """UI sample context with typed access to its sample and comments."""

    sample: JsonObject
    comments: list[JsonObject]


class ReportPreviewMeta(SdkModel):
    """Fingerprint identifying the exact reviewed report inputs."""

    preview_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReportPreviewBody(SdkModel):
    """Rendered preview HTML and clinical rendering context."""

    html: str
    context: JsonObject


class ReportPreview(SdkModel):
    """Report preview requiring explicit review before save."""

    meta: ReportPreviewMeta
    report: ReportPreviewBody


class SavedReportBody(SdkModel):
    """Identifier and artifact names returned by a successful report save."""

    id: str
    file: str


class SavedReport(SdkModel):
    """Confirmed saved report; no automatic save retries are performed."""

    report: SavedReportBody
