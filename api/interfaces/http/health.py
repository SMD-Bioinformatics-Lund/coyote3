"""Health and docs router."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from api.app.runtime_state import app as runtime_app
from api.contracts.system import HealthPayload

router = APIRouter(tags=["system"])


def _external_path(path: str) -> str:
    """Prefix browser-facing redirects with SCRIPT_NAME when mounted below root."""
    root_path = str(runtime_app.config.get("SCRIPT_NAME") or "").rstrip("/")
    return f"{root_path}{path}" if root_path else path


@router.get("/api/v1/health", response_model=HealthPayload)
def health():
    """Return a lightweight health-check payload."""
    return {"status": "ok"}


@router.get("/api/vi/docs", include_in_schema=False)
def docs_alias_vi():
    """Redirect historical docs alias to v1 docs."""
    return RedirectResponse(url=_external_path("/api/v1/docs"), status_code=307)
