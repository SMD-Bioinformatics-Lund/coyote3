"""Internal API routes."""

from fastapi import Request

from api.extensions import store, util
from api.models.user import UserModel
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


@app.get("/api/v1/internal/samples/{sample_ref}/access")
def get_sample_access_internal(sample_ref: str, user_id: str, request: Request):
    _require_internal_token(request)

    sample = store.sample_handler.get_sample(sample_ref)
    if not sample:
        sample = store.sample_handler.get_sample_by_id(sample_ref)
    if not sample:
        raise _api_error(404, "Sample not found")

    user_doc = store.user_handler.user_with_id(user_id)
    if not user_doc or not user_doc.get("is_active", True):
        raise _api_error(404, "User not found")

    role_doc = store.roles_handler.get_role(user_doc.get("role")) or {}
    asp_docs = store.asp_handler.get_all_asps(is_active=True)
    user_model = UserModel.from_mongo(user_doc, role_doc, asp_docs)

    user_assays = set(user_model.assays or [])
    sample_assay = sample.get("assay", "")

    return util.common.convert_to_serializable(
        {
            "status": "ok",
            "sample_ref": sample_ref,
            "sample_assay": sample_assay,
            "allowed": sample_assay in user_assays,
            "sample": sample,
        }
    )
