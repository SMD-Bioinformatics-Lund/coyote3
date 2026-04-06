"""Authentication router."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from api.contracts.auth import (
    ApiAuthLoginRequest,
    ApiPasswordChangeRequest,
    ApiPasswordResetConfirmRequest,
    ApiPasswordResetRequest,
    ApiSessionDeleteResponse,
)
from api.contracts.system import AuthLoginEnvelope, AuthUserEnvelope, WhoamiPayload
from api.extensions import util
from api.security.access import (
    ApiUser,
    create_api_session_token,
    get_api_session_cookie_name,
    get_api_session_cookie_secure,
    get_api_session_ttl_seconds,
    require_access,
    serialize_api_user,
)
from api.security.auth_service import (
    authenticate_credentials,
    build_user_session_payload,
    resolve_user_identity,
    update_user_last_login,
)
from api.security.password_flows import (
    change_local_password,
    consume_password_token_and_set_password,
    issue_password_token_for_user,
)

router = APIRouter(tags=["auth"])


@router.get("/api/v1/auth/whoami", response_model=WhoamiPayload)
def whoami(user: ApiUser = Depends(require_access(min_level=1))):
    """Return the current authenticated user's identity payload."""
    return {
        "username": user.username,
        "role": user.role,
        "access_level": user.access_level,
        "permissions": sorted(user.permissions),
        "denied_permissions": sorted(user.denied_permissions),
    }


def _login_response(payload: ApiAuthLoginRequest):
    """Build the login response and set the session cookie."""
    username = payload.username.strip()
    password = payload.password
    user_doc = authenticate_credentials(username, password)
    if not user_doc:
        raise HTTPException(status_code=401, detail={"status": 401, "error": "Invalid credentials"})

    user_id = resolve_user_identity(user_doc)
    if not user_id:
        raise HTTPException(
            status_code=500, detail={"status": 500, "error": "User identity missing"}
        )
    update_user_last_login(user_id)
    session_token = create_api_session_token(user_id)
    response = JSONResponse(
        status_code=200,
        content=util.common.convert_to_serializable(
            {
                "status": "ok",
                "user": build_user_session_payload(user_doc),
            }
        ),
    )
    response.set_cookie(
        key=get_api_session_cookie_name(),
        value=session_token,
        httponly=True,
        secure=get_api_session_cookie_secure(),
        samesite="lax",
        max_age=get_api_session_ttl_seconds(),
        path="/",
    )
    return response


def _validate_new_password(new_password: str) -> None:
    password = str(new_password or "")
    if len(password) < 10:
        raise HTTPException(
            status_code=400,
            detail={"status": 400, "error": "Password must be at least 10 characters"},
        )
    if not re.search(r"[a-z]", password):
        raise HTTPException(
            status_code=400,
            detail={"status": 400, "error": "Password must include a lowercase letter"},
        )
    if not re.search(r"[A-Z]", password):
        raise HTTPException(
            status_code=400,
            detail={"status": 400, "error": "Password must include an uppercase letter"},
        )
    if not re.search(r"\d", password):
        raise HTTPException(
            status_code=400,
            detail={"status": 400, "error": "Password must include a number"},
        )
    if not re.search(r"[\W_]", password):
        raise HTTPException(
            status_code=400,
            detail={"status": 400, "error": "Password must include a symbol"},
        )


@router.post(
    "/api/v1/auth/sessions",
    response_model=AuthLoginEnvelope,
    status_code=201,
    summary="Create session",
)
def create_auth_session(payload: ApiAuthLoginRequest):
    """Create an authenticated API session."""
    response = _login_response(payload)
    response.status_code = 201
    return response


def _logout_response():
    """Build the logout response and clear the session cookie."""
    response = JSONResponse(status_code=200, content={"status": "ok"})
    response.delete_cookie(key=get_api_session_cookie_name(), path="/")
    return response


@router.delete(
    "/api/v1/auth/sessions/current",
    response_model=ApiSessionDeleteResponse,
    summary="Delete current session",
)
def delete_auth_session():
    """Delete the current authenticated session."""
    return _logout_response()


@router.get(
    "/api/v1/auth/session",
    response_model=AuthUserEnvelope,
    summary="Get current authenticated session",
)
def auth_session(user: ApiUser = Depends(require_access(min_level=1))):
    """Return the current authenticated session payload."""
    return util.common.convert_to_serializable({"status": "ok", "user": serialize_api_user(user)})


@router.post("/api/v1/auth/password/change")
def change_password(payload: ApiPasswordChangeRequest, user: ApiUser = Depends(require_access())):
    """Change local password for the authenticated user."""
    _validate_new_password(payload.new_password)
    out = change_local_password(
        user_id=user.username,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    if out.get("status") != "ok":
        raise HTTPException(
            status_code=400,
            detail={"status": 400, "error": str(out.get("error") or "Unable to change password")},
        )
    return {"status": "ok", "username": user.username}


@router.post("/api/v1/auth/password/reset/request")
def request_password_reset(payload: ApiPasswordResetRequest):
    """Issue a password reset link for a local user.

    Always returns status=ok to avoid account enumeration.
    """
    issue_password_token_for_user(
        login_identifier=payload.username,
        purpose="reset",
        actor_username=None,
    )
    return {"status": "ok"}


@router.post("/api/v1/auth/password/reset/confirm")
def confirm_password_reset(payload: ApiPasswordResetConfirmRequest):
    """Consume one-time token and set a new password."""
    _validate_new_password(payload.new_password)
    out = consume_password_token_and_set_password(
        token=payload.token,
        new_password=payload.new_password,
    )
    if out.get("status") != "ok":
        raise HTTPException(
            status_code=400,
            detail={"status": 400, "error": str(out.get("error") or "Password reset failed")},
        )
    return {"status": "ok"}


async def http_exception_handler(_request: Request, exc: HTTPException):
    """Convert ``HTTPException`` values into the standard JSON error shape."""
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": exc.status_code, "error": str(exc.detail)},
    )
