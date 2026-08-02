"""Authentication API router for Coyote3.

This module provides the necessary endpoints to manage user authentication, session
lifecycles, and password management for the platform. It handles credential verification,
session token issuance, secure logout, and secure password changes.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from api.app.container import ldap_manager, util
from api.app.deps.services import get_admin_user_service
from api.application.accounts.users import UserManagementService
from api.config.constants import AUTH_PROVIDER_LDAP, AUTH_PROVIDER_LOCAL, AUTH_TYPE_OPTIONS
from api.contracts.auth import (
    ApiAuthLoginRequest,
    ApiAuthProvidersResponse,
    ApiPasswordChangeRequest,
    ApiPasswordChangeResponse,
    ApiPasswordResetConfirmRequest,
    ApiPasswordResetRequest,
    ApiProfileUpdateRequest,
    ApiProfileUpdateResponse,
    ApiSessionDeleteResponse,
    ApiStatusResponse,
)
from api.contracts.system import AuthLoginEnvelope, AuthUserEnvelope, WhoamiPayload
from api.interfaces.http.tags import TAG_AUTH
from api.security.access import (
    ApiUser,
    create_api_session_token,
    delete_api_session_token,
    get_api_session_cookie_name,
    get_api_session_cookie_samesite,
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

router = APIRouter(tags=[TAG_AUTH])


def _provider_from_login_identifier(login_identifier: str) -> str:
    return AUTH_PROVIDER_LDAP if "@" in str(login_identifier or "") else AUTH_PROVIDER_LOCAL


def _available_auth_providers() -> list[str]:
    """Return authentication providers enabled for this deployment."""
    return list(AUTH_TYPE_OPTIONS)


@router.get("/api/v1/auth/whoami", response_model=WhoamiPayload)
def whoami(user: ApiUser = Depends(require_access())):
    """Retrieve the current authenticated user's identity payload.

    Provides the active session's identity context, including username, assigned role,
    access level, and effective role-granted permissions. This
    endpoint is used by the client application to initialize user-specific contexts
    and enforce role-based UI boundaries.

    Args:
        user (ApiUser): The authenticated API user automatically resolved from the session context.

    Returns:
        WhoamiPayload: A structured payload containing the current user's identity and permission metadata.
    """
    return {
        "username": user.username,
        "roles": sorted(user.roles),
        "role": user.role,
        "access_level": user.access_level,
        "permissions": sorted(user.permissions),
    }


def _login_response(payload: ApiAuthLoginRequest):
    """Construct a successful login response and issue a secure session cookie.

    Validates user credentials against the internal authentication service.
    Upon successful verification, issues an encrypted session token, updates
    the user's last login timestamp, and sets an HTTP-only secure cookie for
    subsequent API authentication.

    Args:
        payload (ApiAuthLoginRequest): The login request payload containing username and password.

    Returns:
        JSONResponse: The HTTP response containing the user session payload and the required `Set-Cookie` header.

    Raises:
        HTTPException: Raises 401 Unauthorized for invalid credentials, or 500 Internal Server Error if the user identity cannot be resolved.
    """
    username = payload.username.strip()
    password = payload.password
    provider = str(payload.provider or "").strip().lower()
    if provider not in _available_auth_providers():
        raise HTTPException(
            status_code=400,
            detail={"status": 400, "error": "Selected login provider is unavailable"},
        )
    if provider == AUTH_PROVIDER_LDAP and not ldap_manager.is_configured:
        raise HTTPException(
            status_code=503,
            detail={
                "status": 503,
                "error": "LDAP login is enabled but directory configuration is unavailable",
            },
        )
    user_doc = authenticate_credentials(username, password, provider=provider)
    if not user_doc:
        from api.app.deps.services import get_audit_service

        audit = get_audit_service()
        if audit is not None:
            audit.record(
                "auth.login.failed",
                "Authentication attempt was rejected",
                severity="warning",
                category="security",
                outcome="failure",
                actor=username or "anonymous",
                resource_type="session",
                tags=["authentication", "login", "failed-login"],
            )
        raise HTTPException(status_code=401, detail={"status": 401, "error": "Invalid credentials"})

    identity_username = resolve_user_identity(user_doc)
    if not identity_username:
        raise HTTPException(
            status_code=500, detail={"status": 500, "error": "User identity missing"}
        )
    update_user_last_login(identity_username)
    session_token = create_api_session_token(identity_username, provider=provider)
    from api.app.deps.services import get_audit_service

    audit = get_audit_service()
    if audit is not None:
        audit.record(
            "auth.login.succeeded",
            "User signed in",
            category="security",
            actor=identity_username,
            provider=provider,
            resource_type="session",
            tags=["authentication", "login"],
        )
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
        samesite=get_api_session_cookie_samesite(),
        max_age=get_api_session_ttl_seconds(),
        path="/",
    )
    return response


@router.get("/api/v1/auth/providers", response_model=ApiAuthProvidersResponse)
def auth_providers_read():
    """Return the center-enabled login mechanisms for the public login screen."""
    return {"providers": _available_auth_providers()}


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
    """Create an authenticated API session.

    Acts as the primary entry point for user login. It delegates credential
    verification and session establishment to internal authentication handlers,
    resulting in a secure cookie payload returned to the client.

    Args:
        payload (ApiAuthLoginRequest): The data transfer object containing the user's login credentials.

    Returns:
        Response: The HTTP 201 response containing the created session data and secure cookie headers.
    """
    response = _login_response(payload)
    response.status_code = 201
    return response


def _logout_response(request: Request | None = None):
    """Construct a logout response and invalidate the active session cookie.

    Clears the target HTTP-only session cookie by intentionally issuing a
    cookie deletion directive to the client's browser, effectively terminating
    the active session.

    Returns:
        JSONResponse: A positive status confirmation with the cookie-clearing header.
    """
    username = "anonymous"
    if request is not None:
        user = getattr(request.state, "authenticated_user", None)
        username = getattr(user, "username", None) or username
        auth_header = (request.headers.get("Authorization") or "").strip()
        bearer_token = (
            auth_header.split(" ", 1)[1].strip()
            if auth_header.lower().startswith("bearer ")
            else None
        )
        delete_api_session_token(bearer_token or request.cookies.get(get_api_session_cookie_name()))
        from api.app.deps.services import get_audit_service

        audit = get_audit_service()
        if audit is not None:
            audit.record(
                "auth.logout.succeeded",
                "User signed out",
                category="security",
                actor=username,
                resource_type="session",
                tags=["authentication", "logout"],
            )
    response = JSONResponse(status_code=200, content={"status": "ok"})
    response.delete_cookie(key=get_api_session_cookie_name(), path="/")
    return response


@router.delete(
    "/api/v1/auth/sessions/current",
    response_model=ApiSessionDeleteResponse,
    summary="Delete current session",
)
def delete_auth_session(request: Request = None):
    """Terminate the current authenticated session.

    Serves as the designated logout endpoint. Explicitly clears the client's
    session cookie to ensure subsequent API calls natively require re-authentication.

    Returns:
        ApiSessionDeleteResponse: A normalized confirmation indicating successful session termination.
    """
    return _logout_response(request)


@router.get(
    "/api/v1/auth/session",
    response_model=AuthUserEnvelope,
    summary="Get current authenticated session",
)
def auth_session(user: ApiUser = Depends(require_access())):
    """Retrieve the payload of the active authenticated session.

    Validates the requester's active session token and exposes the parsed
    ApiUser profile natively.

    Args:
        user (ApiUser): The active user automatically resolved through the session token.

    Returns:
        AuthUserEnvelope: A standard envelope containing the serialized API user profile representation.
    """
    return util.common.convert_to_serializable({"status": "ok", "user": serialize_api_user(user)})


@router.patch("/api/v1/auth/profile", response_model=ApiProfileUpdateResponse)
def update_current_profile(
    payload: ApiProfileUpdateRequest,
    user: ApiUser = Depends(require_access()),
    service: UserManagementService = Depends(get_admin_user_service),
):
    """Update safe identity fields for the authenticated account."""
    return util.common.convert_to_serializable(
        service.update_own_profile(username=user.username, payload=payload.model_dump())
    )


@router.post("/api/v1/auth/password/change", response_model=ApiPasswordChangeResponse)
def change_password(payload: ApiPasswordChangeRequest, user: ApiUser = Depends(require_access())):
    """Change the local password for the active authenticated user.

    Enforces commercial-security password complexity constraints. Requires valid
    verification of the current password before adopting the new password vector.

    Args:
        payload (ApiPasswordChangeRequest): The payload containing current and requested new password.
        user (ApiUser): The active context user requesting the mutation.

    Returns:
        dict: A successful operation acknowledgement containing the affected user's username.

    Raises:
        HTTPException: Raises 400 Bad Request if standard complexity checks or current password verification fails.
    """
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


@router.post("/api/v1/auth/password/reset/request", response_model=ApiStatusResponse)
def request_password_reset(payload: ApiPasswordResetRequest):
    """Issue a secure, time-limited password reset link for a local user.

    Accepts an incoming reset request for an identifier and generates a corresponding
    one-time cryptographic reset token. Note that to prevent system account enumeration,
    this endpoint deliberately returns a positive status regardless of target existence.

    Args:
        payload (ApiPasswordResetRequest): The identifier payload targeting the intended account.

    Returns:
        dict: A generic success response to avoid exposing valid user identifiers.
    """
    issue_password_token_for_user(
        login_identifier=payload.username,
        purpose="reset",
        actor_username=None,
    )
    return {"status": "ok"}


@router.post("/api/v1/auth/password/reset/confirm", response_model=ApiStatusResponse)
def confirm_password_reset(payload: ApiPasswordResetConfirmRequest):
    """Consume a valid one-time token to securely set a new password.

    Validates the supplied reset token for proper signatures and expiration.
    If recognized and active, it modifies the targeted user record's authentication hash.
    This enforces the same password complexity standard applied to direct changes.

    Args:
        payload (ApiPasswordResetConfirmRequest): The token and new password combination.

    Returns:
        dict: A successful operation acknowledgement.

    Raises:
        HTTPException: Raises 400 Bad Request upon token invalidation, expiration, or failure to meet password constraints.
    """
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
    """Normalize an HTTPException into standard JSON API error representation.

    Overrides the default FastAPI error handlers to ensure the platform returns API
    errors with consistent structural keys (`status`, `error`) to client applications.

    Args:
        _request (Request): The contexting active HTTP request.
        exc (HTTPException): The triggered FastAPI HTTP exception.

    Returns:
        JSONResponse: Expected commercial-grade JSON response matching internal structures.
    """
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": exc.status_code, "error": str(exc.detail)},
    )
