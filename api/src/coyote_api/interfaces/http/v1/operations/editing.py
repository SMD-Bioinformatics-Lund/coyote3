# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Document editing leases with resource-specific authorization."""

from typing import Literal

from coyote.application.operations.application import CoyoteApplication
from coyote.contracts.editing import EditLeaseRequest, EditLeaseStatus
from fastapi import APIRouter, Depends

from coyote_api.app.deps.application import get_application
from coyote_api.interfaces.http.tags import TAG_ADMIN_OPERATIONS
from coyote_api.security.access import ApiUser, require_access

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
