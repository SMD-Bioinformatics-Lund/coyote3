"""Internal token-protected router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.contracts.internal import IsglMetaPayload, RoleLevelsPayload
from api.core.internal.ports import InternalRepository
from api.deps.repositories import get_internal_repository
from api.extensions import util
from api.security.access import _require_internal_token

router = APIRouter(tags=["internal"])


@router.get("/api/v1/internal/roles/levels", response_model=RoleLevelsPayload)
def get_role_levels_internal(request: Request, repository: InternalRepository = Depends(get_internal_repository)):
    """Return role levels internal.

    Args:
        request (Request): Value for ``request``.
        repository (InternalRepository): Value for ``repository``.

    Returns:
        The function result.
    """
    _require_internal_token(request)
    role_levels = {
        role.get("role_id"): role.get("level", 0)
        for role in repository.get_all_roles()
        if role.get("role_id")
    }
    return util.common.convert_to_serializable({"status": "ok", "role_levels": role_levels})


@router.get("/api/v1/internal/isgl/{isgl_id}/meta", response_model=IsglMetaPayload)
def get_isgl_meta_internal(
    isgl_id: str,
    request: Request,
    repository: InternalRepository = Depends(get_internal_repository),
):
    """Return isgl meta internal.

    Args:
        isgl_id (str): Value for ``isgl_id``.
        request (Request): Value for ``request``.
        repository (InternalRepository): Value for ``repository``.

    Returns:
        The function result.
    """
    _require_internal_token(request)
    return util.common.convert_to_serializable(
        {
            "status": "ok",
            "isgl_id": isgl_id,
            "is_adhoc": bool(repository.is_isgl_adhoc(isgl_id)),
            "display_name": repository.get_isgl_display_name(isgl_id),
        }
    )
