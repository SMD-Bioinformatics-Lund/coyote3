"""Internal API routes."""

from fastapi import Request

from api.extensions import store, util
from api.app import _api_error, _require_internal_token, app


@app.get("/api/v1/internal/roles/levels")
def get_role_levels_internal(request: Request):
    _require_internal_token(request)
    role_levels = {
        role["_id"]: role.get("level", 0)
        for role in store.roles_handler.get_all_roles()
    }
    return util.common.convert_to_serializable(
        {
            "status": "ok",
            "role_levels": role_levels,
        }
    )


@app.get("/api/v1/internal/isgl/{isgl_id}/meta")
def get_isgl_meta_internal(isgl_id: str, request: Request):
    _require_internal_token(request)
    return util.common.convert_to_serializable(
        {
            "status": "ok",
            "isgl_id": isgl_id,
            "is_adhoc": bool(store.isgl_handler.is_isgl_adhoc(isgl_id)),
            "display_name": store.isgl_handler.get_isgl_display_name(isgl_id),
        }
    )
