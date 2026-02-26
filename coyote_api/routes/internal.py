"""Internal API routes."""

from fastapi import Request
from pydantic import BaseModel

from coyote.extensions import store, util
from coyote_api.app import _api_error, _require_internal_token, app
from coyote_api.services.auth import authenticate_credentials, build_user_session_payload


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
