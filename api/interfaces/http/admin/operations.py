"""Canonical admin utility routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from api.app.container import util
from api.app.deps.services import get_audit_service
from api.app.runtime_state import app as runtime_app
from api.application.audit.service import AuditService
from api.application.ingest.tokens import issue_audited_ingest_token
from api.config.security import get_internal_api_token, get_runtime_environment
from api.contracts.admin import (
    AdminAuditPayload,
    AdminSchemasPayload,
    IngestTokenIssueRequest,
    IngestTokenIssueResponse,
)
from api.contracts.schemas.registry import COLLECTION_MODEL_ADAPTERS
from api.interfaces.http.tags import TAG_ADMIN_OPERATIONS
from api.security.access import ApiUser, require_access

router = APIRouter(tags=[TAG_ADMIN_OPERATIONS])


@router.post(
    "/api/v1/admin/ingest-tokens", response_model=IngestTokenIssueResponse, status_code=201
)
def create_ingest_token(
    payload: IngestTokenIssueRequest,
    response: Response,
    user: ApiUser = Depends(require_access(permission="ingest.token:issue")),
    audit: AuditService = Depends(get_audit_service),
):
    """Issue an expiring pipeline token with the ingest.token:issue permission.

    Authenticate with a user session or bearer session token. Cookie sessions
    require X-CSRF-Token. Internal and ingestion tokens cannot issue credentials.
    Save the returned token securely; it is returned only by this request.
    The server selects the environment and synchronous sample-ingestion scope.
    """
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    try:
        return issue_audited_ingest_token(
            secret=get_internal_api_token(runtime_app.config),
            environment=get_runtime_environment(runtime_app.config),
            hours=payload.expires_hours,
            actor=user,
            audit=audit,
        )
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Token issuance is unavailable") from None


def _schema_payload(collection: str, adapter: Any) -> dict[str, Any]:
    """Build a serializable schema metadata row."""
    try:
        json_schema = adapter.json_schema()
    except Exception:
        json_schema = {}
    return {
        "collection": collection,
        "title": json_schema.get("title") or collection,
        "required": json_schema.get("required") or [],
        "properties": sorted((json_schema.get("properties") or {}).keys()),
        "schema": json_schema,
    }


@router.get("/api/v1/admin/schemas", response_model=AdminSchemasPayload)
def admin_schemas_read(
    q: str = "",
    user: ApiUser = Depends(require_access(permission="schema:list")),
):
    """Return registered document schema contracts for admin inspection."""
    _ = user
    needle = q.strip().lower()
    rows = [
        _schema_payload(collection, adapter)
        for collection, adapter in sorted(COLLECTION_MODEL_ADAPTERS.items())
        if not needle or needle in collection.lower()
    ]
    return util.common.convert_to_serializable({"schemas": rows, "total": len(rows)})


@router.get("/api/v1/admin/audit", response_model=AdminAuditPayload)
def admin_audit_read(
    limit: int = Query(default=200, ge=1, le=1000),
    user: ApiUser = Depends(require_access(permission="audit_log:view")),
    audit_service: AuditService = Depends(get_audit_service),
):
    """Return recent durable audit events."""
    _ = user
    return util.common.convert_to_serializable(audit_service.recent_events(limit=limit))
