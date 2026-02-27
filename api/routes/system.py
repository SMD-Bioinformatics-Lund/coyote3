"""System and auth routes for the FastAPI app."""

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from api.app import (
    ApiUser,
    app,
    create_api_session_token,
    get_api_session_cookie_name,
    get_api_session_cookie_secure,
    get_api_session_ttl_seconds,
    require_access,
    serialize_api_user,
)
from api.extensions import store, util
from api.services.auth import authenticate_credentials, build_user_session_payload


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": exc.status_code, "error": str(exc.detail)},
    )


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}


@app.get("/api/vi/docs", include_in_schema=False)
def docs_alias_vi():
    return RedirectResponse(url="/api/v1/docs", status_code=307)


@app.get("/api/v1/auth/whoami")
def whoami(user: ApiUser = Depends(require_access(min_level=1))):
    return {
        "username": user.username,
        "role": user.role,
        "access_level": user.access_level,
        "permissions": sorted(user.permissions),
        "denied_permissions": sorted(user.denied_permissions),
    }


class ApiAuthLoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/v1/auth/login")
def auth_login(payload: ApiAuthLoginRequest):
    username = payload.username.strip()
    password = payload.password
    user_doc = authenticate_credentials(username, password)
    if not user_doc:
        raise HTTPException(status_code=401, detail={"status": 401, "error": "Invalid credentials"})

    user_id = str(user_doc.get("_id"))
    store.user_handler.update_user_last_login(user_id)
    session_token = create_api_session_token(user_id)
    response = JSONResponse(
        status_code=200,
        content=util.common.convert_to_serializable(
            {
                "status": "ok",
                "user": build_user_session_payload(user_doc),
                "session_token": session_token,
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


@app.post("/api/v1/auth/logout")
def auth_logout():
    response = JSONResponse(status_code=200, content={"status": "ok"})
    response.delete_cookie(key=get_api_session_cookie_name(), path="/")
    return response


@app.get("/api/v1/auth/me")
def auth_me(user: ApiUser = Depends(require_access(min_level=1))):
    return util.common.convert_to_serializable({"status": "ok", "user": serialize_api_user(user)})
