"""Managed ingestion credential requests and public metadata; secrets are returned once."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ServiceTokenOperation = Literal[
    "sample_bundle", "sample_upload", "sample_bundle_async", "sample_upload_async", "job_status"
]
SERVICE_TOKEN_PREFIX = "coy3_service_"


class TokenScopeCreate(BaseModel):
    """Request explicit ingestion operations, assays and clinical environments."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    operations: list[ServiceTokenOperation] = Field(min_length=1, max_length=5)
    asp_ids: list[str] = Field(min_length=1, max_length=200)
    environments: list[str] = Field(min_length=1, max_length=20)
    expires_hours: int = Field(default=720, ge=1, le=8760, strict=True)

    @field_validator("name")
    @classmethod
    def strip_text(cls, value: str) -> str:
        """Reject blank names and owners after trimming whitespace."""
        if not value.strip():
            raise ValueError("A nonblank value is required")
        return value.strip()

    @field_validator("asp_ids", "environments")
    @classmethod
    def explicit_scopes(cls, values: list[str]) -> list[str]:
        """Require explicit scopes; wildcard access cannot be issued."""
        if any(not value.strip() or "*" in value for value in values):
            raise ValueError("Select explicit scopes; wildcards and blank values are not allowed")
        return sorted({value.strip().lower() for value in values})


class ServiceTokenCreate(TokenScopeCreate):
    """Request an administrator-managed token for an explicitly selected owner."""

    owner: str = Field(min_length=1, max_length=100)

    @field_validator("owner")
    @classmethod
    def normalize_owner(cls, value: str) -> str:
        """Require a nonblank canonical account name."""
        if not value.strip():
            raise ValueError("An owner is required")
        return value.strip().lower()


class ServiceTokenMetadata(BaseModel):
    """Public credential identity and lifecycle fields without its credential hash."""

    token_id: str
    kind: Literal["service", "personal"]
    name: str
    owner: str
    operations: list[ServiceTokenOperation]
    asp_ids: list[str]
    environments: list[str]
    audience: str
    created_by: str
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    revoked_by: str | None = None


class ServiceTokenIssued(BaseModel):
    """One-time credential response paired with its nonsecret metadata."""

    token: str = Field(repr=False)
    metadata: ServiceTokenMetadata


class ServiceTokenList(BaseModel):
    """Bounded list of managed service-token metadata."""

    items: list[ServiceTokenMetadata]


class ServiceTokenOptions(BaseModel):
    """Actual active owners, assays and configured clinical environment choices."""

    owners: list[dict[str, str]]
    assays: list[dict[str, str]]
    environments: list[str]
    operations: list[ServiceTokenOperation]


class PersonalTokenCreate(TokenScopeCreate):
    """Request a token for the authenticated user; owner cannot be supplied by the caller."""
