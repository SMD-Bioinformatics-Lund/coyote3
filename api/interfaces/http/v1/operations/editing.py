"""Document editing leases with resource-specific authorization."""

from typing import Literal

from fastapi import APIRouter, Depends

from api.app.deps.application import get_application
from api.interfaces.http.tags import TAG_ADMIN_OPERATIONS
from api.security.access import ApiUser, require_access
from coyote3.application.operations.application import CoyoteApplication
from coyote3.contracts.editing import EditLeaseRequest, EditLeaseStatus

router = APIRouter(prefix="/api/v1/editing", tags=[TAG_ADMIN_OPERATIONS])


@router.post("/{kind}/{identity}/{action}", response_model=EditLeaseStatus | None)
def edit_session(
    kind: str,
    identity: str,
    action: Literal["acquire", "renew", "release"],
    payload: EditLeaseRequest,
    user: ApiUser = Depends(require_access()),
    application: CoyoteApplication = Depends(get_application),
) -> EditLeaseStatus | None:
    """Manage a per-document editor lease; requires the resource's current edit permission.

    Existing record protections still apply. Renewal cannot reclaim an expired lease.
    """
    return application.editing.session(kind, identity, payload.editor_id, action)
