"""Internal API routes."""

from fastapi import Request

from coyote.extensions import store, util
from coyote_api.app import _api_error, _require_internal_token, app


def _mutation_payload(sample_id: str, resource: str, resource_id: str, action: str) -> dict:
    return {
        "status": "ok",
        "sample_id": str(sample_id),
        "resource": resource,
        "resource_id": str(resource_id),
        "action": action,
        "meta": {"status": "updated"},
    }


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
