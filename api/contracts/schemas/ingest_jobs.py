"""Durable sample-ingest job state and transaction completion receipts."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from api.contracts.schemas.base import _StrictCollectionDocBase


class IngestJobDoc(_StrictCollectionDocBase):
    """Durable ingest job with source payload, lease, attempts, and completion result."""

    kind: Literal["sample_bundle", "insert_document", "insert_documents", "upsert_document"] = (
        "sample_bundle"
    )
    state: Literal["pending", "running", "succeeded", "failed"] = "pending"
    source_payload: dict[str, Any] | None = None
    update_existing: bool = False
    increment: bool = False
    staging_dir: str | None = None
    created_at: datetime
    updated_at: datetime
    lease_until: datetime | None = None
    lease_token: str | None = None
    attempts: int = Field(default=0, ge=0)
    result: dict[str, Any] | None = None
    error: str | None = None
    submitted_by: str
