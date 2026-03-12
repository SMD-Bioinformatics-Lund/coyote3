"""Authentication router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from api.contracts.auth import ApiAuthLoginRequest, ApiSessionDeleteResponse
from api.contracts.system import AuthLoginEnvelope, AuthUserEnvelope, HealthPayload, WhoamiPayload
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

router = APIRouter(tags=["auth"])


@router.get("/api/v1/auth/whoami", response_model=WhoamiPayload)
def whoami(user: ApiUser = Depends(require_access(min_level=1))):
    return {
        "username": user.username,
        "role": user.role,
        "access_level": user.access_level,
        "permissions": sorted(user.permissions),
        "denied_permissions": sorted(user.denied_permissions),
    }


def _login_response(payload: ApiAuthLoginRequest):
    username = payload.username.strip()
    password = payload.password
    user_doc = authenticate_credentials(username, password)
    if not user_doc:
        raise HTTPException(status_code=401, detail={"status": 401, "error": "Invalid credentials"})

    user_id = resolve_user_identity(user_doc)
    if not user_id:
        raise HTTPException(status_code=500, detail={"status": 500, "error": "User identity missing"})
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


@router.post("/api/v1/auth/sessions", response_model=AuthLoginEnvelope, status_code=201, summary="Create session")
def create_auth_session(payload: ApiAuthLoginRequest):
    response = _login_response(payload)
    response.status_code = 201
    return response


def _logout_response():
    response = JSONResponse(status_code=200, content={"status": "ok"})
    response.delete_cookie(key=get_api_session_cookie_name(), path="/")
    return response


@router.delete("/api/v1/auth/sessions/current", response_model=ApiSessionDeleteResponse, summary="Delete current session")
def delete_auth_session():
    return _logout_response()


@router.get("/api/v1/auth/session", response_model=AuthUserEnvelope, summary="Get current authenticated session")
def auth_session(user: ApiUser = Depends(require_access(min_level=1))):
    return util.common.convert_to_serializable({"status": "ok", "user": serialize_api_user(user)})


async def http_exception_handler(_request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": exc.status_code, "error": str(exc.detail)},
    )
