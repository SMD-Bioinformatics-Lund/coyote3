"""Authentication and access control helpers for API routes."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass

from fastapi import HTTPException, Request

from api.app.deps.repositories import (
    get_permissions_repository,
    get_roles_repository,
    get_sample_repository,
    get_user_repository,
)
from api.app.deps.services import get_api_session_repository
from api.app.runtime_state import app as runtime_app
from api.app.runtime_state import reset_current_user, set_current_user
from api.domain.core.models.user import UserModel
from api.security.audit_events import emit_access_event
from api.security.auth_service import _load_user_access_context
from api.security.policy import build_access_policy
from api.settings import (
    get_api_session_cookie_name as settings_session_cookie_name,
)
from api.settings import (
    get_api_session_cookie_samesite as settings_session_cookie_samesite,
)
from api.settings import (
    get_api_session_cookie_secure as settings_session_cookie_secure,
)
from api.settings import (
    get_api_session_ttl_seconds as settings_session_ttl_seconds,
)
from api.settings import (
    get_internal_api_token,
)

PUBLIC_API_EXACT_PATHS = {
    "/api/v1/health",
    "/api/v1/auth/sessions",
    "/api/v1/auth/sessions/current",
    "/api/v1/auth/password/reset/request",
    "/api/v1/auth/password/reset/confirm",
    "/api/v1/docs",
    "/api/v1/openapi.json",
    "/api/v1/redoc",
}
PUBLIC_API_PREFIX_PATHS = (
    "/api/v1/public/",
    "/api/v1/internal/",
)


@dataclass
class ApiUser:
    """Provide the api user type."""

    id: str
    email: str
    fullname: str
    username: str
    roles: list[str]
    role: str
    access_level: int
    permissions: list[str]
    assays: list[str]
    assay_groups: list[str]
    envs: list[str]
    asp_map: dict
    auth_type: list[str]
    must_change_password: bool = False

    @property
    def is_superuser(self) -> bool:
        """Return whether the authenticated user is a superuser."""
        return "superuser" in set(self.roles)


def _api_error(
    status_code: int,
    message: str,
    details: str | None = None,
    *,
    category: str | None = None,
    hint: str | None = None,
) -> HTTPException:
    """Build a normalized API ``HTTPException``.

    Args:
        status_code: HTTP status code to return.
        message: User-facing error message.

    Returns:
        HTTPException: Normalized error payload.
    """
    return HTTPException(
        status_code=status_code,
        detail={
            "status": status_code,
            "error": message,
            "details": details,
            "category": category,
            "hint": hint,
        },
    )


def is_public_api_path(path: str) -> bool:
    """Return whether an API path is publicly accessible.

    Args:
        path: Request path to evaluate.

    Returns:
        bool: ``True`` when the path skips authentication.
    """
    if path in PUBLIC_API_EXACT_PATHS:
        return True
    if path.startswith(PUBLIC_API_PREFIX_PATHS):
        return True
    # Static metadata route intentionally exposed for public catalog UI helpers.
    if path.startswith("/api/v1/common/gene/") and path.endswith("/info"):
        return True
    return False


def _http_exception_message(exc: HTTPException) -> str:
    """Extract a log-friendly message from an ``HTTPException``.

    Args:
        exc: Exception to summarize.

    Returns:
        str: Error message derived from the exception detail.
    """
    detail = exc.detail
    if isinstance(detail, dict):
        return str(detail.get("error") or detail.get("details") or detail)
    return str(detail)


def _audit_access_event(
    *,
    status: str,
    reason: str,
    request: Request | None = None,
    user: ApiUser | None = None,
    permission: str | None = None,
    sample_id: str | None = None,
    extra: dict | None = None,
) -> None:
    """Emit an access-control audit event.

    Args:
        status: Access outcome.
        reason: Explanation for the decision.
        request: Active request, when available.
        user: Authenticated user, when available.
        permission: Required permission, when applicable.
        sample_id: Related sample identifier.
        extra: Additional structured metadata to emit.
    """
    emit_access_event(
        status=status,
        reason=reason,
        request=request,
        username=user.username if user else None,
        roles=user.roles if user else None,
        role=user.role if user else None,
        permission=permission,
        sample_id=sample_id,
        extra=extra,
    )


def get_api_session_cookie_name() -> str:
    """Return the configured API session cookie name.

    Returns:
        str: Cookie name used for API sessions.
    """
    return settings_session_cookie_name(runtime_app.config)


def get_api_session_ttl_seconds() -> int:
    """Return the configured API session lifetime.

    Returns:
        int: Session lifetime in seconds.
    """
    return settings_session_ttl_seconds(runtime_app.config)


def get_api_session_cookie_secure() -> bool:
    """Return whether the API session cookie must be secure.

    Returns:
        bool: ``True`` when the cookie must only be sent over HTTPS.
    """
    return settings_session_cookie_secure(runtime_app.config)


def get_api_session_cookie_samesite() -> str:
    """Return the API session cookie SameSite policy."""
    return settings_session_cookie_samesite(runtime_app.config)


def create_api_session_token(username: str, *, provider: str | None = None) -> str:
    """Create an opaque Mongo-backed API session token for a user.

    Args:
        username: Username to embed in the token.

    Returns:
        str: Opaque session token.
    """
    user_doc = get_user_repository().user_with_id(str(username).strip().lower())
    if not user_doc or not user_doc.get("is_active", True):
        raise _api_error(401, "Login required")
    user = api_user_from_user_doc(user_doc)
    session_provider = provider or (user.auth_type[0] if user.auth_type else "ldap")
    session = get_api_session_repository().create(user, provider=session_provider)
    return session.token


def delete_api_session_token(token: str | None) -> None:
    """Delete an opaque API session token when present."""
    if token:
        get_api_session_repository().delete(token)


def api_user_from_user_doc(user_doc: dict) -> ApiUser:
    """Build an ``ApiUser`` from the stored user document.

    Args:
        user_doc: Stored user document.

    Returns:
        ApiUser: Runtime user model for request handling.
    """
    role_docs, asp_docs = _load_user_access_context(user_doc)
    user_model = UserModel.from_auth_payload(user_doc, role_docs, asp_docs)
    return ApiUser(
        id=str(user_model.username),
        email=user_model.email,
        fullname=user_model.fullname,
        username=user_model.username,
        roles=list(user_model.roles),
        role=user_model.role,
        access_level=user_model.access_level,
        permissions=list(user_model.permissions),
        assays=list(user_model.assays),
        assay_groups=list(user_model.assay_groups),
        envs=list(user_model.envs),
        asp_map=dict(user_model.asp_map),
        auth_type=list(getattr(user_model, "auth_type", ["ldap"]) or ["ldap"]),
        must_change_password=bool(getattr(user_model, "must_change_password", False)),
    )


def serialize_api_user(user: ApiUser) -> dict:
    """Serialize an ``ApiUser`` into a response-safe payload.

    Args:
        user: Runtime user model to serialize.

    Returns:
        dict: Serialized user payload.
    """
    return {
        "_id": user.username,
        "email": user.email,
        "fullname": user.fullname,
        "username": user.username,
        "roles": sorted(user.roles),
        "role": user.role,
        "access_level": user.access_level,
        "permissions": sorted(user.permissions),
        "assays": sorted(user.assays),
        "assay_groups": sorted(user.assay_groups),
        "envs": sorted(user.envs),
        "asp_map": user.asp_map,
        "auth_type": user.auth_type,
        "must_change_password": bool(user.must_change_password),
    }


def _extract_api_session_token(request: Request) -> str | None:
    """Extract an API session token from the request.

    Args:
        request: Active request.

    Returns:
        str | None: Bearer token or session cookie value.
    """
    auth_header = (request.headers.get("Authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        if token:
            return token
    return request.cookies.get(get_api_session_cookie_name())


def _decode_session_user(request: Request) -> ApiUser:
    """Decode and validate the authenticated API user.

    Args:
        request: Active request.

    Returns:
        ApiUser: Authenticated runtime user.
    """
    api_token = _extract_api_session_token(request)
    if api_token:
        session = get_api_session_repository().get(api_token)
        if session is None:
            raise _api_error(401, "Login required")
        return session.user
    raise _api_error(401, "Login required")


def _enforce_access(
    user: ApiUser,
    permission: str | None = None,
    context: dict | None = None,
) -> None:
    """Enforce permission and optional resource-scope requirements for a user.

    Args:
        user: Authenticated user to evaluate.
        permission: Required permission, when applicable.
        context: Resource attributes for ABAC scope checks.
    """
    if user.is_superuser:
        return
    if not permission and not context:
        return

    policy = build_access_policy(
        user=user,
        roles_repository=get_roles_repository(),
        permissions_repository=get_permissions_repository(),
    )

    if permission and not policy.permission_allowed(user, permission, context=context):
        raise _api_error(
            403,
            "Access denied",
            "You do not satisfy the required permission policy.",
            category="auth",
        )
    if context and not policy.scope_allowed(user, context):
        raise _api_error(
            403,
            "Access denied",
            "You do not satisfy the required attribute-scope policy.",
            category="scope",
        )


def require_authenticated(request: Request) -> ApiUser:
    """Require a valid authenticated session without applying route-level RBAC."""
    return _decode_session_user(request)


def resolve_request_user(request: Request) -> ApiUser | None:
    """
    Best-effort request user resolver.

    Returns the authenticated user for valid session context, otherwise None.
    Unlike `require_authenticated`, this helper never raises.
    """
    try:
        return _decode_session_user(request)
    except HTTPException:
        return None


def require_access(permission: str | None = None):
    """Build a dependency that enforces route-level access requirements.

    Args:
        permission: Required permission, when applicable.

    Returns:
        Callable: FastAPI dependency that yields the authenticated user.
    """

    def dep(request: Request) -> Generator[ApiUser, None, None]:
        """Resolve, authorize, and yield the authenticated user.

        Args:
            request: Active request.

        Returns:
            Generator[ApiUser, None, None]: Authorized user dependency result.
        """
        user: ApiUser | None = None
        try:
            user = _decode_session_user(request)
            _enforce_access(user, permission=permission)
        except HTTPException as exc:
            _audit_access_event(
                status="denied",
                reason=_http_exception_message(exc),
                request=request,
                user=user,
                permission=permission,
            )
            raise
        _audit_access_event(
            status="authorized",
            reason="Access granted",
            request=request,
            user=user,
            permission=permission,
        )
        token = set_current_user(user)
        try:
            yield user
        finally:
            reset_current_user(token)

    return dep


def _get_sample_for_api(sample_id: str, user: ApiUser, request: Request | None = None):
    """Return a sample after enforcing sample-assay access rules.

    Args:
        sample_id: Sample identifier to resolve.
        user: Authenticated user requesting access.
        request: Active request, when available.

    Returns:
        dict: Sample payload authorized for the user.
    """
    sample_repository = get_sample_repository()
    sample = sample_repository.get_sample(sample_id)
    if not sample:
        sample = sample_repository.get_sample_by_id(sample_id)
    if not sample:
        _audit_access_event(
            status="denied",
            reason="Sample not found",
            request=request,
            user=user,
            sample_id=sample_id,
            extra={"check": "sample_lookup"},
        )
        raise _api_error(404, "Sample not found", category="not_found")

    sample_assay = sample.get("assay", "")
    if not user.is_superuser:
        policy = build_access_policy(
            user=user,
            roles_repository=get_roles_repository(),
            permissions_repository=get_permissions_repository(),
        )
        sample_scope = {
            "assay": sample_assay,
            "profile": sample.get("profile") or sample.get("environment"),
            "assay_group": sample.get("assay_group"),
        }
        scope_allowed = policy.scope_allowed(user, sample_scope)
    else:
        scope_allowed = True

    if not scope_allowed and sample_assay not in set(user.assays or []):
        _audit_access_event(
            status="denied",
            reason="Forbidden",
            request=request,
            user=user,
            sample_id=sample_id,
            extra={"sample_assay": sample_assay},
        )
        raise _api_error(
            403,
            f"Sample '{sample_id}' is outside your assay scope",
            (
                f"Sample '{sample_id}' belongs to assay '{sample_assay}', "
                f"which is not assigned to user '{user.username}'."
            ),
            category="scope",
            hint="Ask an administrator to assign the assay to your user, or use a superuser account.",
        )
    if not scope_allowed:
        _audit_access_event(
            status="denied",
            reason="Forbidden",
            request=request,
            user=user,
            sample_id=sample_id,
            extra={
                "sample_assay": sample_assay,
                "sample_profile": sample.get("profile") or sample.get("environment"),
                "sample_assay_group": sample.get("assay_group"),
            },
        )
        raise _api_error(
            403,
            f"Sample '{sample_id}' is outside your access scope",
            "The sample attributes do not match your assigned assay, environment, or assay-group scope.",
            category="scope",
            hint="Ask an administrator to update your sample access scope.",
        )
    return sample


def _require_internal_token(request: Request) -> None:
    """Validate the internal API token header.

    Args:
        request: Active request.
    """
    try:
        expected = get_internal_api_token(runtime_app.config)
    except RuntimeError:
        expected = ""
    provided = request.headers.get("X-Coyote-Internal-Token")
    if not expected or not provided or provided != expected:
        raise _api_error(403, "Forbidden", category="auth")
