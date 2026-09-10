"""Authenticated browser error reporting."""

from fastapi import APIRouter, Depends

from api.application.notifications.client_errors import record_client_error
from api.contracts.client_errors import ClientErrorRequest, ClientErrorResponse
from api.interfaces.http.tags import TAG_SYSTEM
from api.security.access import ApiUser, require_access

router = APIRouter(tags=[TAG_SYSTEM])


@router.post("/api/v1/client-errors", response_model=ClientErrorResponse, include_in_schema=False)
def client_error(payload: ClientErrorRequest, user: ApiUser = Depends(require_access())):
    """Record UI errors for signed-in users under the normal CSRF and rate limits."""
    record_client_error(message=payload.message, stack=payload.stack, username=user.username)
    return ClientErrorResponse()
