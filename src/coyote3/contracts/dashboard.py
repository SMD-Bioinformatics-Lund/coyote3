"""Dashboard route API contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DashboardAdminInsightsPayload(BaseModel):
    """Represent flexible administrative dashboard insight payloads."""

    model_config = ConfigDict(extra="allow")


class DashboardRefreshQueuedPayload(BaseModel):
    """Represent an asynchronously queued dashboard metrics refresh."""

    status: str
    task_id: str


class DashboardMetricPayload(BaseModel):
    """Represent one independently cached dashboard metric payload."""

    model_config = ConfigDict(extra="allow")

    metric_meta: dict[str, Any]


class DashboardMetricRefreshRequest(BaseModel):
    """Select dashboard metrics for an immediate background refresh."""

    metrics: list[str] = Field(default_factory=list)
