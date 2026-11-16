# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Canonical admin utility routes."""

from __future__ import annotations

from coyote.application.operations.system import Credentials, Traceability
from coyote.contracts.admin import (
    AdminAuditPayload,
    AdminSchemasPayload,
    IngestTokenIssueRequest,
    IngestTokenIssueResponse,
)
from fastapi import APIRouter, Depends, Query, Response

from coyote_api.app.deps.application import get_credentials, get_traceability
from coyote_api.app.utilities.serialization import convert_to_serializable
from coyote_api.interfaces.http.tags import TAG_ADMIN_OPERATIONS
from coyote_api.security.access import ApiUser, require_access

router = APIRouter(tags=[TAG_ADMIN_OPERATIONS])


@router.post(
    "/api/v1/admin/ingest-tokens", response_model=IngestTokenIssueResponse, status_code=201
)
def create_ingest_token(
    payload: IngestTokenIssueRequest,
    response: Response,
    user: ApiUser = Depends(require_access(permission="ingest.token:issue")),
    service: Credentials = Depends(get_credentials),
):
    """Issue an expiring pipeline token with the ingest.token:issue permission.

    Authenticate with a user session or bearer session token. Cookie sessions
    require X-CSRF-Token. Internal and ingestion tokens cannot issue credentials.
    Save the returned token securely; it is returned only by this request.
    The server selects the environment and synchronous sample-ingestion scope.
    """
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return service.issue_ingest_token(payload.expires_hours)


@router.get("/api/v1/admin/schemas", response_model=AdminSchemasPayload)
def admin_schemas_read(
    q: str = "",
    user: ApiUser = Depends(require_access(permission="schema:list")),
    service: Traceability = Depends(get_traceability),
):
    """Return registered document schema contracts for admin inspection."""
    return convert_to_serializable(service.schemas(q))


@router.get("/api/v1/admin/audit", response_model=AdminAuditPayload)
def admin_audit_read(
    limit: int = Query(default=200, ge=1, le=1000),
    ingestion_only: bool = Query(default=False),
    user: ApiUser = Depends(require_access(permission="audit_log:view")),
    service: Traceability = Depends(get_traceability),
):
    """Return recent durable audit events."""
    return convert_to_serializable(service.events(limit, ingestion_only=ingestion_only))
