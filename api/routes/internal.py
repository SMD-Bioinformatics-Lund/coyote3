"""Internal API routes."""

from fastapi import Request

from api.contracts.internal import IsglMetaPayload, RoleLevelsPayload
from api.core.internal.ports import InternalRepository
from api.extensions import util
from api.app import app
from api.infra.repositories.internal_mongo import MongoInternalRepository
from api.security.access import _require_internal_token


_internal_repo_instance: InternalRepository | None = None


def _internal_repo() -> InternalRepository:
    global _internal_repo_instance
    if _internal_repo_instance is None:
        _internal_repo_instance = MongoInternalRepository()
    return _internal_repo_instance


@app.get("/api/v1/internal/roles/levels", response_model=RoleLevelsPayload)
def get_role_levels_internal(request: Request):
    _require_internal_token(request)
    role_levels = {
        role["_id"]: role.get("level", 0)
        for role in _internal_repo().get_all_roles()
    }
    return util.common.convert_to_serializable(
        {
            "status": "ok",
            "role_levels": role_levels,
        }
    )


@app.get("/api/v1/internal/isgl/{isgl_id}/meta", response_model=IsglMetaPayload)
def get_isgl_meta_internal(isgl_id: str, request: Request):
    _require_internal_token(request)
    return util.common.convert_to_serializable(
        {
            "status": "ok",
            "isgl_id": isgl_id,
            "is_adhoc": bool(_internal_repo().is_isgl_adhoc(isgl_id)),
            "display_name": _internal_repo().get_isgl_display_name(isgl_id),
        }
    )

