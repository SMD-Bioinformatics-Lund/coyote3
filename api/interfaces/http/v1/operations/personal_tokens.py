"""Session-authenticated personal ingestion credential management."""

from fastapi import APIRouter, Depends, Response

from api.app.deps.application import get_credentials
from api.interfaces.http.tags import TAG_AUTH
from api.security.access import ApiUser, require_access
from coyote3.application.operations.system import Credentials
from coyote3.contracts.service_tokens import (
    PersonalTokenCreate,
    ServiceTokenIssued,
    ServiceTokenList,
    ServiceTokenMetadata,
    ServiceTokenOptions,
)

router = APIRouter(prefix="/api/v1/auth/personal-tokens", tags=[TAG_AUTH])


@router.get("", response_model=ServiceTokenList)
def list_personal_tokens(
    user: ApiUser = Depends(require_access()), service: Credentials = Depends(get_credentials)
):
    """List the current session user's personal-token metadata, excluding all secrets."""
    return service.personal_tokens()


@router.get("/options", response_model=ServiceTokenOptions)
def personal_token_options(
    user: ApiUser = Depends(require_access()), service: Credentials = Depends(get_credentials)
):
    """Return currently authorized personal-token assay/environment choices."""
    return service.personal_token_options()


@router.post("", response_model=ServiceTokenIssued, status_code=201)
def create_personal_token(
    payload: PersonalTokenCreate,
    response: Response,
    user: ApiUser = Depends(require_access()),
    service: Credentials = Depends(get_credentials),
):
    """Create a token for the session user with selected access bounded by current permissions."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return service.create_personal_token(payload)


@router.delete("/{token_id}", response_model=ServiceTokenMetadata)
def revoke_personal_token(
    token_id: str,
    user: ApiUser = Depends(require_access()),
    service: Credentials = Depends(get_credentials),
):
    """Revoke only the session user's own personal token; admins use the managed-token page."""
    return service.revoke_personal_token(token_id)
