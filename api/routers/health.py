"""Health and docs router."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from api.contracts.system import HealthPayload

router = APIRouter(tags=["system"])


@router.get("/api/v1/health", response_model=HealthPayload)
def health():
    return {"status": "ok"}


@router.get("/api/vi/docs", response_model=HealthPayload, include_in_schema=False)
def docs_alias_vi():
    return RedirectResponse(url="/api/v1/docs", status_code=307)
