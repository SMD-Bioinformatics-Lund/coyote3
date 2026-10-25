"""Session-owned leases for exclusive editing of existing documents."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EditLeaseRequest(BaseModel):
    """Identify one browser editor session independently of the user's login."""

    model_config = ConfigDict(extra="forbid")
    editor_id: UUID


class EditLeaseStatus(BaseModel):
    """Public ownership metadata without exposing another editor's lease token."""

    resource_type: str
    resource_id: str
    owned: bool = False
    owner: str | None = None
    expires_at: datetime | None = None
    renew_after_seconds: int = Field(default=30, ge=1)
