"""Authentication API router for Coyote3.

This module provides the necessary endpoints to manage user authentication, session
lifecycles, and password management for the platform. It handles credential verification,
session token issuance, secure logout, and secure password changes.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from api.app.container import ldap_manager, util
from api.app.deps.application import get_account, get_password_recovery
from api.contracts.auth import (
    ApiAuthLoginRequest,
    ApiAuthProvidersResponse,
    ApiPasswordChangeResponse,
    ApiPasswordResetRequest,
    ApiProfileUpdateResponse,
    ApiSessionDeleteResponse,
    ApiStatusResponse,
    ApiUiSettingsUpdateResponse,
)
from api.contracts.system import AuthLoginEnvelope, WhoamiPayload
from api.interfaces.http.tags import TAG_AUTH
from api.security.access import (
    ApiUser,
    create_api_session,
    delete_api_session_token,
    get_api_session_cookie_name,
    get_api_session_cookie_samesite,
    get_api_session_cookie_secure,
    get_api_session_ttl_seconds,
    get_request_api_session,
    require_access,
    serialize_api_user,
)
from api.security.auth_service import (
    authenticate_credentials,
    build_user_session_payload,
    resolve_user_identity,
    update_user_last_login,
)
from coyote3.application.operations.account import Account, PasswordRecovery
from coyote3.config.constants import AUTH_PROVIDER_LDAP, AUTH_PROVIDER_LOCAL, AUTH_TYPE_OPTIONS
from coyote3.contracts.auth import (
    ApiPasswordChangeRequest,
    ApiPasswordResetConfirmRequest,
    ApiProfileUpdateRequest,
    ApiUiSettingsUpdateRequest,
)

router = APIRouter(tags=[TAG_AUTH])
logger = logging.getLogger(__name__)


def _provider_from_login_identifier(login_identifier: str) -> str:
    """Choose LDAP for identifiers containing an at sign, otherwise local login.

    Args:
        login_identifier: Submitted login identifier; an empty or false value
            selects local authentication.

    Returns:
        AUTH_PROVIDER_LDAP when the string contains @, otherwise AUTH_PROVIDER_LOCAL.
    """
    return AUTH_PROVIDER_LDAP if "@" in str(login_identifier or "") else AUTH_PROVIDER_LOCAL


def _available_auth_providers() -> list[str]:
    """Return authentication providers enabled for this deployment."""
    return list(AUTH_TYPE_OPTIONS)


@router.get(
    "/api/v1/auth/whoami", response_model=WhoamiPayload, summary="Get your current user and access"
)
def whoami(request: Request, user: ApiUser = Depends(require_access())):
    """Check which Coyote3 account is signed in and what access it has.

    Returns your name, roles, permissions, interface settings and session CSRF token.
    Use the CSRF token when making changes with a browser session cookie. The
    response describes the current session; it does not change your account.
    """
    return {
        "username": user.username,
        "firstname": user.firstname,
        "fullname": user.fullname,
        "roles": sorted(user.roles),
        "role": user.role,
        "access_level": user.access_level,
        "permissions": sorted(user.permissions),
        "ui_settings": dict(user.ui_settings),
        "csrf_token": get_request_api_session(request).csrf_token,
    }


def _login_response(payload: ApiAuthLoginRequest, request: Request | None = None):
    """Construct a successful login response and issue a secure session cookie.

    Validates user credentials against the internal authentication service.
    Upon successful verification, issues an opaque server-side session token, updates
    the user's last login timestamp, and sets an HTTP-only secure cookie for
    subsequent API authentication.

    Args:
        payload (ApiAuthLoginRequest): The login request payload containing username and password.
        request: Request supplying the forwarded protocol or URL scheme for
            cookie security; None leaves scheme selection to session configuration.

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
    session = create_api_session(user_doc, provider=provider)
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
                "csrf_token": session.csrf_token,
            }
        ),
    )
    forwarded_scheme = ""
    if request is not None:
        forwarded_scheme = request.headers.get("X-Forwarded-Proto", "").split(",", 1)[0].strip()
    request_scheme = forwarded_scheme or (request.url.scheme if request is not None else None)
    secure_cookie = get_api_session_cookie_secure(request_scheme=request_scheme)
    if not secure_cookie:
        logger.warning(
            "api_session_cookie_http_fallback scheme=%s; use HTTPS outside local development",
            request_scheme or "unknown",
        )

    response.set_cookie(
        key=get_api_session_cookie_name(),
        value=session.token,
        httponly=True,
        secure=secure_cookie,
        samesite=get_api_session_cookie_samesite(),
        max_age=get_api_session_ttl_seconds(),
        path="/",
    )
    return response


@router.get("/api/v1/auth/providers", response_model=ApiAuthProvidersResponse)
def auth_providers_read():
    """Return the center-enabled login mechanisms for the public login screen."""
    return {"providers": _available_auth_providers()}


@router.post(
    "/api/v1/auth/sessions",
    response_model=AuthLoginEnvelope,
    status_code=201,
    summary="Create session",
)
def create_auth_session(payload: ApiAuthLoginRequest, request: Request):
    """Create an authenticated API session.

    Acts as the primary entry point for user login. It delegates credential
    verification and session establishment to internal authentication handlers,
    resulting in a secure cookie payload returned to the client.

    \u000c

    Args:
        payload (ApiAuthLoginRequest): The data transfer object containing the user's login credentials.
        request: Request forwarded to the login helper to determine cookie security.

    Returns:
        Response: The HTTP 201 response containing the created session data and secure cookie headers.
    """
    response = _login_response(payload, request=request)
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
    response_model=AuthLoginEnvelope,
    summary="Get current authenticated session",
)
def auth_session(request: Request, user: ApiUser = Depends(require_access())):
    """Retrieve the payload of the active authenticated session.

    Validates the requester's active session token and exposes the parsed
    ApiUser profile natively.

    \u000c

    Args:
        request: Request whose session cookie resolves the session and CSRF token.
        user (ApiUser): The active user automatically resolved through the session token.

    Returns:
        AuthLoginEnvelope: The active user profile and browser CSRF token.
    """
    session = get_request_api_session(request)
    return util.common.convert_to_serializable(
        {
            "status": "ok",
            "user": serialize_api_user(user),
            "csrf_token": session.csrf_token,
        }
    )


@router.patch("/api/v1/auth/profile", response_model=ApiProfileUpdateResponse)
def update_current_profile(
    payload: ApiProfileUpdateRequest,
    user: ApiUser = Depends(require_access()),
    service: Account = Depends(get_account),
):
    """Update safe identity fields for the authenticated account."""
    return util.common.convert_to_serializable(service.update_profile(payload.model_dump()))


@router.patch(
    "/api/v1/users/me/ui-settings",
    response_model=ApiUiSettingsUpdateResponse,
    summary="Update current user interface settings",
)
def update_current_ui_settings(
    payload: ApiUiSettingsUpdateRequest,
    user: ApiUser = Depends(require_access()),
    service: Account = Depends(get_account),
):
    """Persist validated interface preferences for the authenticated account."""
    return util.common.convert_to_serializable(
        service.update_ui_settings(payload.model_dump(exclude_unset=True))
    )


@router.post("/api/v1/auth/password/change", response_model=ApiPasswordChangeResponse)
def change_password(
    payload: ApiPasswordChangeRequest,
    user: ApiUser = Depends(require_access()),
    service: Account = Depends(get_account),
):
    """Change the local password for the active authenticated user.

    Verify the current password and validate the new password before replacing it.
    First-login changes also require matching confirmation. Existing sessions become
    invalid when the stored password changes.

    \u000c

    Args:
        payload (ApiPasswordChangeRequest): The payload containing current and requested new password.
        user (ApiUser): The active context user requesting the mutation.

    Returns:
        dict: A successful operation acknowledgement containing the affected user's username.

    Raises:
        HTTPException: Raises 400 Bad Request if standard complexity checks or current password verification fails.
    """
    return service.change_password(payload)


@router.post("/api/v1/auth/password/reset/request", response_model=ApiStatusResponse)
def request_password_reset(
    payload: ApiPasswordResetRequest, service: PasswordRecovery = Depends(get_password_recovery)
):
    """Issue a secure, time-limited password reset link for a local user.

    Accepts an incoming reset request for an identifier and generates a corresponding
    one-time cryptographic reset token. Note that to prevent system account enumeration,
    this endpoint deliberately returns a positive status regardless of target existence.

    \u000c

    Args:
        payload (ApiPasswordResetRequest): The identifier payload targeting the intended account.

    Returns:
        dict: A generic success response to avoid exposing valid user identifiers.
    """
    return service.request_reset(payload.username)


@router.post("/api/v1/auth/password/reset/confirm", response_model=ApiStatusResponse)
def confirm_password_reset(
    payload: ApiPasswordResetConfirmRequest,
    service: PasswordRecovery = Depends(get_password_recovery),
):
    """Consume a valid one-time token to securely set a new password.

    Validates the supplied reset token for proper signatures and expiration.
    If recognized and active, it modifies the targeted user record's authentication hash.
    This enforces the same password complexity standard applied to direct changes.

    \u000c

    Args:
        payload (ApiPasswordResetConfirmRequest): The token and new password combination.

    Returns:
        dict: A successful operation acknowledgement.

    Raises:
        HTTPException: Raises 400 Bad Request upon token invalidation, expiration, or failure to meet password constraints.
    """
    return service.confirm_reset(payload)


async def http_exception_handler(_request: Request, exc: HTTPException):
    """Normalize an HTTPException into standard JSON API error representation.

    Overrides the default FastAPI error handlers to ensure the platform returns API
    errors with consistent structural keys (`status`, `error`) to client applications.

    Args:
        _request: Incoming request with correlation context.
        exc: HTTP error carrying client-safe details and protocol headers.

    Returns:
        JSON response preserving the HTTP status and required response headers.
    """
    from api.interfaces.http.errors import error_response

    detail = exc.detail if isinstance(exc.detail, dict) else {"error": str(exc.detail)}
    return error_response(
        _request,
        exc.status_code,
        detail.get("error") or detail.get("message"),
        details=detail.get("details"),
        category=detail.get("category"),
        hint=detail.get("hint"),
        headers=exc.headers,
    )
