"""Health and docs router."""

from __future__ import annotations

from fastapi import APIRouter

from api.contracts.system import HealthPayload
from api.interfaces.http.tags import TAG_SYSTEM

router = APIRouter(tags=[TAG_SYSTEM])


@router.get("/api/v1/health", response_model=HealthPayload)
def health():
    """Return a lightweight health-check payload."""
    return {"status": "ok"}
