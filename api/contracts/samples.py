"""Sample and coverage-mutation route contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SampleMutationPayload(BaseModel):
    status: str
    sample_id: str
    resource: str
    resource_id: str
    action: str
    meta: dict[str, Any]


class CoverageBlacklistStatusPayload(BaseModel):
    status: str
    message: str
