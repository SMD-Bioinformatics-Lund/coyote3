"""Common HTTP contracts for REST responses and validation errors."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

PayloadT = TypeVar("PayloadT")


class ApiSuccessPayload(BaseModel, Generic[PayloadT]):
    """Represent the standard success envelope for new API responses."""

    status: str = "ok"
    payload: PayloadT
    meta: dict[str, Any] = Field(default_factory=dict)


class ApiPageMeta(BaseModel):
    """Represent pagination metadata shared by list endpoints."""

    page: int = 1
    per_page: int = 50
    total: int = 0
    has_next: bool = False
    has_previous: bool = False


class ApiListPayload(BaseModel, Generic[PayloadT]):
    """Represent the standard list envelope for new API responses."""

    status: str = "ok"
    items: list[PayloadT] = Field(default_factory=list)
    pagination: ApiPageMeta = Field(default_factory=ApiPageMeta)
    meta: dict[str, Any] = Field(default_factory=dict)


class ApiMutationPayload(BaseModel):
    """Represent the standard mutation/change response envelope."""

    status: str = "ok"
    resource: str
    resource_id: str | None = None
    action: str
    message: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class ApiErrorPayload(BaseModel):
    """Represent the api error payload."""

    status: int
    error: str
    details: Any | None = None


class ApiValidationIssue(BaseModel):
    """Provide the api validation issue type."""

    field: str
    message: str


class ApiValidationErrorPayload(ApiErrorPayload):
    """Represent the api validation error payload."""

    error: str = "Validation failed"
    details: list[ApiValidationIssue] = Field(default_factory=list)
