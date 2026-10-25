"""Canonical admin utility routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from api.app.container import util
from api.app.deps.application import get_credentials, get_installation, get_traceability
from api.contracts.demo_installation import DemoInstallationPlan, DemoInstallResult
from api.interfaces.http.tags import TAG_ADMIN_OPERATIONS
from api.security.access import ApiUser, require_access
from api.services.installation import Installation
from coyote3.application.operations.system import Credentials, Traceability
from coyote3.contracts.admin import (
    AdminAuditPayload,
    AdminSchemasPayload,
    IngestTokenIssueRequest,
    IngestTokenIssueResponse,
)

router = APIRouter(tags=[TAG_ADMIN_OPERATIONS])


@router.get(
    "/api/v1/admin/demo-installation", response_model=DemoInstallationPlan, include_in_schema=False
)
def demo_installation_plan(
    user: ApiUser = Depends(require_access(permission="demo:install")),
    service: Installation = Depends(get_installation),
):
    """Inspect packaged demo configuration and sample status with demo:install permission."""
    return service.plan()


@router.post(
    "/api/v1/admin/demo-installation/starter",
    response_model=DemoInstallResult,
    include_in_schema=False,
)
def install_demo_starter(
    user: ApiUser = Depends(require_access(permission="demo:install")),
    service: Installation = Depends(get_installation),
):
    """Install connected starter configuration and its first synthetic sample; requires demo:install."""
    return service.starter()


@router.post(
    "/api/v1/admin/demo-installation/configuration",
    response_model=DemoInstallResult,
    include_in_schema=False,
)
def install_demo_configuration(
    user: ApiUser = Depends(require_access(permission="demo:install")),
    service: Installation = Depends(get_installation),
):
    """Install synthetic testing configuration; existing fixture identities are never replaced."""
    return service.configuration()


@router.post(
    "/api/v1/admin/demo-installation/samples/{key}",
    response_model=DemoInstallResult,
    include_in_schema=False,
)
def install_demo_sample(
    key: str,
    user: ApiUser = Depends(require_access(permission="demo:install")),
    service: Installation = Depends(get_installation),
):
    """Ingest an allowlisted synthetic sample with demo:install permission."""
    return service.sample(key)


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
    return util.common.convert_to_serializable(service.schemas(q))


@router.get("/api/v1/admin/audit", response_model=AdminAuditPayload)
def admin_audit_read(
    limit: int = Query(default=200, ge=1, le=1000),
    user: ApiUser = Depends(require_access(permission="audit_log:view")),
    service: Traceability = Depends(get_traceability),
):
    """Return recent durable audit events."""
    return util.common.convert_to_serializable(service.events(limit))
