"""Shared HTTP contracts for REST responses and validation errors."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ApiErrorPayload(BaseModel):
    status: int
    error: str
    details: Any | None = None


class ApiValidationIssue(BaseModel):
    field: str
    message: str


class ApiValidationErrorPayload(ApiErrorPayload):
    error: str = "Validation failed"
    details: list[ApiValidationIssue] = Field(default_factory=list)

