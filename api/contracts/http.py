"""Shared HTTP contracts for REST responses and validation errors."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ApiErrorPayload(BaseModel):
    """Represent the api error payload.
    """
    status: int
    error: str
    details: Any | None = None


class ApiValidationIssue(BaseModel):
    """Provide the api validation issue type.
    """
    field: str
    message: str


class ApiValidationErrorPayload(ApiErrorPayload):
    """Represent the api validation error payload.
    """
    error: str = "Validation failed"
    details: list[ApiValidationIssue] = Field(default_factory=list)

