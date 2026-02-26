"""Internal API routes."""

from fastapi import Request
from pydantic import BaseModel

from coyote.extensions import store, util
from coyote.models.user import UserModel
from api.app import _api_error, _require_internal_token, app
from api.services.auth import authenticate_credentials, build_user_session_payload


def _mutation_payload(sample_id: str, resource: str, resource_id: str, action: str) -> dict:
    return {
        "status": "ok",
        "sample_id": str(sample_id),
        "resource": resource,
        "resource_id": str(resource_id),
        "action": action,
        "meta": {"status": "updated"},
    }


class InternalAuthLoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/v1/internal/auth/login")
def login_internal(payload: InternalAuthLoginRequest, request: Request):
    _require_internal_token(request)
    username = payload.username.strip()
    password = payload.password
    user_doc = authenticate_credentials(username, password)
    if not user_doc:
        raise _api_error(401, "Invalid credentials")

    user_id = str(user_doc.get("_id"))
    store.user_handler.update_user_last_login(user_id)
    return util.common.convert_to_serializable(
        {
            "status": "ok",
            "user": build_user_session_payload(user_doc),
        }
    )


@app.get("/api/v1/internal/users/{user_id}/session")
def get_user_session_internal(user_id: str, request: Request):
    _require_internal_token(request)
    user_doc = store.user_handler.user_with_id(user_id)
    if not user_doc or not user_doc.get("is_active", True):
        raise _api_error(404, "User not found")
    return util.common.convert_to_serializable(
        {
            "status": "ok",
            "user": build_user_session_payload(user_doc),
        }
    )


@app.post("/api/v1/internal/users/{user_id}/last_login")
def update_user_last_login_internal(user_id: str, request: Request):
    _require_internal_token(request)
    user_doc = store.user_handler.user_with_id(user_id)
    if not user_doc:
        raise _api_error(404, "User not found")
    store.user_handler.update_user_last_login(user_id)
    return util.common.convert_to_serializable(
        _mutation_payload("internal", resource="user", resource_id=user_id, action="update_last_login")
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
