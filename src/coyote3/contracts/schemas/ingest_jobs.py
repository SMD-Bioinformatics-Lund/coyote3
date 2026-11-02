"""Durable sample-ingest job state and transaction completion receipts."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from coyote3.contracts.schemas.base import _StrictCollectionDocBase


class IngestCredentialScope(BaseModel):
    """Nonsecret scope retained after source payload cleanup for job-status authorization."""

    model_config = ConfigDict(extra="forbid")
    asp_id: str
    environment: str


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
    credential_id: str | None = None
    credential_owner: str | None = None
    credential_operation: Literal["sample_bundle_async", "sample_upload_async"] | None = None
    credential_scope: IngestCredentialScope | None = None

    @model_validator(mode="after")
    def complete_credential_reference(self) -> "IngestJobDoc":
        """Require a complete public credential reference for managed sample jobs."""
        values = (
            self.credential_id,
            self.credential_owner,
            self.credential_operation,
            self.credential_scope,
        )
        if any(value is not None for value in values) and (
            not all(values) or self.kind != "sample_bundle"
        ):
            raise ValueError(
                "Managed jobs require a complete credential identity, operation and scope"
            )
        return self
