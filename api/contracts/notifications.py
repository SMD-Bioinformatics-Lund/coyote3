"""API contracts for recipient-scoped notifications and broadcasts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

NotificationTone = Literal["success", "info", "warning", "error"]
NotificationCategory = Literal["application", "feature", "maintenance", "security", "warning"]


class NotificationResourcePayload(BaseModel):
    """Optional resource context displayed with a notification."""

    type: str | None = None
    id: str | None = None
    name: str | None = None
    sample_name: str | None = None
    finding: str | None = None


class NotificationItemPayload(BaseModel):
    """One notification as visible to the current user."""

    id: str
    tone: NotificationTone
    category: NotificationCategory
    title: str
    message: str = ""
    source: str = ""
    resource: NotificationResourcePayload | None = None
    created_at: str
    created_by: str
    read: bool


class NotificationListPayload(BaseModel):
    """Current user's notification inbox."""

    notifications: list[NotificationItemPayload]
    unread_count: int


class NotificationChangePayload(BaseModel):
    """Notification state-change acknowledgement."""

    status: str = "ok"
    changed: int = 0


class NotificationRecipientPayload(BaseModel):
    """Active user available as a broadcast recipient."""

    username: str
    name: str
    email: str = ""


class NotificationRolePayload(BaseModel):
    """Active role available as a broadcast audience."""

    role_id: str
    label: str
    user_count: int = 0


class NotificationRecipientsPayload(BaseModel):
    """Available notification recipients."""

    users: list[NotificationRecipientPayload]
    roles: list[NotificationRolePayload] = Field(default_factory=list)


class NotificationBroadcastRequest(BaseModel):
    """Administrative broadcast request."""

    audience: Literal["all", "roles", "selected"]
    recipients: list[str] = Field(default_factory=list)
    role_ids: list[str] = Field(default_factory=list)
    tone: NotificationTone = "info"
    category: NotificationCategory = "application"
    title: str = Field(min_length=3, max_length=160)
    message: str = Field(min_length=1, max_length=5000)

    @field_validator("recipients")
    @classmethod
    def normalize_recipients(cls, value: list[str]) -> list[str]:
        """Normalize recipient usernames while preserving order."""
        return list(dict.fromkeys(str(item).strip().lower() for item in value if str(item).strip()))

    @field_validator("role_ids")
    @classmethod
    def normalize_role_ids(cls, value: list[str]) -> list[str]:
        """Normalize role identifiers while preserving order."""
        return list(dict.fromkeys(str(item).strip().lower() for item in value if str(item).strip()))

    @model_validator(mode="after")
    def validate_selected_recipients(self) -> "NotificationBroadcastRequest":
        """Require at least one username for a selected-user broadcast."""
        if self.audience == "selected" and not self.recipients:
            raise ValueError("At least one recipient is required for a selected-user broadcast")
        if self.audience == "roles" and not self.role_ids:
            raise ValueError("At least one role is required for a role broadcast")
        return self


class NotificationBroadcastResponse(BaseModel):
    """Administrative broadcast creation result."""

    status: str = "ok"
    notification_id: str
    audience: str
    recipient_count: int
