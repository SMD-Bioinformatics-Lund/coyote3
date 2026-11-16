# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Admin-managed ingestion identities with one-time secret disclosure."""

from coyote.application.operations.system import Credentials
from coyote.contracts.service_tokens import (
    ServiceTokenCreate,
    ServiceTokenIssued,
    ServiceTokenList,
    ServiceTokenMetadata,
    ServiceTokenOptions,
)
from fastapi import APIRouter, Depends, Response

from coyote_api.app.deps.application import get_credentials
from coyote_api.interfaces.http.tags import TAG_ADMIN_ACCESS
from coyote_api.security.access import ApiUser, require_access

router = APIRouter(prefix="/api/v1/admin/service-tokens", tags=[TAG_ADMIN_ACCESS])


@router.get("", response_model=ServiceTokenList)
def list_tokens(
    user: ApiUser = Depends(require_access(permission="ingest.token:issue")),
    service: Credentials = Depends(get_credentials),
):
    """List public credential metadata with ingest.token:issue; hashes are never returned."""
    return service.service_tokens()


@router.get("/options", response_model=ServiceTokenOptions)
def token_options(
    user: ApiUser = Depends(require_access(permission="ingest.token:issue")),
    service: Credentials = Depends(get_credentials),
):
    """List active owners and scopes available to ingestion-token administrators."""
    return service.service_token_options()


@router.post("", response_model=ServiceTokenIssued, status_code=201)
def create_token(
    payload: ServiceTokenCreate,
    response: Response,
    user: ApiUser = Depends(require_access(permission="ingest.token:issue")),
    service: Credentials = Depends(get_credentials),
):
    """Create a scoped credential with ingest.token:issue and disclose its secret once."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return service.create_service_token(payload)


@router.delete("/{token_id}", response_model=ServiceTokenMetadata)
def revoke_token(
    token_id: str,
    user: ApiUser = Depends(require_access(permission="ingest.token:issue")),
    service: Credentials = Depends(get_credentials),
):
    """Revoke a managed credential with ingest.token:issue, retaining its public history."""
    return service.revoke_service_token(token_id)
