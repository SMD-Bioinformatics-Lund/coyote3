"""Internal API route contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from api.contracts.schemas.samples import SamplesDoc


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


class InternalIngestSampleBundleRequest(BaseModel):
    sample: SamplesDoc | None = None
    yaml_content: str | None = None
    update_existing: bool = False
    increment: bool = False


class InternalIngestSampleBundlePayload(BaseModel):
    """Represent internal sample+analysis bundle ingest response payload."""

    status: str
    sample_id: str
    sample_name: str
    written: dict[str, int]
    data_counts: dict[str, int | bool]


class InternalIngestAcknowledgementPayload(BaseModel):
    """Represent the terminal acknowledgement used by externally managed manifests."""

    status: str
    sample_name: str | None = None
    sample_id: str | None = None
    message: str
    result: InternalIngestSampleBundlePayload | None = None


class InternalTaskSubmitPayload(BaseModel):
    """Represent an enqueued internal background task."""

    status: str
    task_id: str
    task_name: str
    queue: str


class InternalTaskStatusPayload(BaseModel):
    """Represent Celery task state and optional result metadata."""

    status: str
    task_id: str
    state: str
    ready: bool
    successful: bool | None = None
    result: dict[str, Any] | list[Any] | str | int | float | bool | None = None
    error: str | None = None


class InternalCollectionInsertRequest(BaseModel):
    """Represent request body for single document insert."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "collection": "permissions",
                "document": {
                    "permission_id": "sample:read",
                    "label": "View samples",
                    "category": "Sample Management",
                    "description": "Allows the user to view samples within their assigned scope.",
                    "is_active": True,
                },
                "ignore_duplicate": True,
            }
        }
    )

    collection: str
    document: dict[str, Any]
    ignore_duplicate: bool = False


class InternalCollectionBulkInsertRequest(BaseModel):
    """Represent request body for bulk document insert."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "collection": "permissions",
                "documents": [
                    {
                        "permission_id": "sample:read",
                        "label": "View samples",
                        "category": "Sample Management",
                    },
                ],
                "ignore_duplicates": True,
            }
        }
    )

    collection: str
    documents: list[dict[str, Any]]
    ignore_duplicates: bool = False


class InternalCollectionInsertPayload(BaseModel):
    """Represent collection insert response payload."""

    status: str
    collection: str
    inserted_count: int
    inserted_id: str | None = None


class InternalCollectionUpsertRequest(BaseModel):
    """Represent request body for replace/update in one collection."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "collection": "permissions",
                "match": {"permission_id": "sample:read"},
                "document": {
                    "permission_id": "sample:read",
                    "label": "View samples",
                    "category": "Sample Management",
                    "is_active": True,
                },
                "upsert": False,
            }
        }
    )

    collection: str
    match: dict[str, Any]
    document: dict[str, Any]
    upsert: bool = False


class InternalCollectionUpsertPayload(BaseModel):
    """Represent collection replace/update response payload."""

    status: str
    collection: str
    matched_count: int
    modified_count: int
    upserted_id: str | None = None


class InternalCollectionSupportPayload(BaseModel):
    """Represent supported collection list response payload."""

    status: str
    collections: list[str]


class InternalCollectionStatusPayload(BaseModel):
    """Represent collection occupancy for first-deployment bootstrap decisions."""

    status: str
    collection: str
    document_count: int
    empty: bool


class InternalCollectionUploadPayload(BaseModel):
    """Represent multipart collection-upload ingest response payload."""

    status: str
    collection: str
    mode: str
    inserted_count: int | None = None
    inserted_id: str | None = None
    matched_count: int | None = None
    modified_count: int | None = None
    upserted_id: str | None = None
