"""Authentication and access control helpers for API routes."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from functools import lru_cache

from fastapi import HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from api.core.models.user import UserModel
from api.runtime_state import app as runtime_app
from api.runtime_state import reset_current_user, set_current_user
from api.security.audit_events import emit_access_event
from api.security.repository import get_security_repository
from api.settings import (
    get_api_secret_key,
    get_api_session_salt,
    get_internal_api_token,
)
from api.settings import (
    get_api_session_cookie_name as settings_session_cookie_name,
)
from api.settings import (
    get_api_session_cookie_secure as settings_session_cookie_secure,
)
from api.settings import (
    get_api_session_ttl_seconds as settings_session_ttl_seconds,
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
    role: str
    access_level: int
    permissions: list[str]
    denied_permissions: list[str]
    assays: list[str]
    assay_groups: list[str]
    envs: list[str]
    asp_map: dict
    auth_type: str = "coyote3"
    must_change_password: bool = False


def _api_error(status_code: int, message: str) -> HTTPException:
    """Api error.

    Args:
            status_code: Status code.
            message: Message.

    Returns:
            The  api error result.
    """
    return HTTPException(status_code=status_code, detail={"status": status_code, "error": message})


def is_public_api_path(path: str) -> bool:
    """Return whether public api path is true.

    Args:
        path (str): Value for ``path``.

    Returns:
        bool: The function result.
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
    """Http exception message.

    Args:
            exc: Exc.

    Returns:
            The  http exception message result.
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
    min_level: int | None = None,
    min_role: str | None = None,
    sample_id: str | None = None,
    extra: dict | None = None,
) -> None:
    """Audit access event.

    Args:
            status: Status. Keyword-only argument.
            reason: Reason. Keyword-only argument.
            request: Request. Keyword-only argument.
            user: User. Keyword-only argument.
            permission: Permission. Keyword-only argument.
            min_level: Min level. Keyword-only argument.
            min_role: Min role. Keyword-only argument.
            sample_id: Sample id. Keyword-only argument.
            extra: Extra. Keyword-only argument.

    Returns:
            None.
    """
    emit_access_event(
        status=status,
        reason=reason,
        request=request,
        user_id=user.id if user else None,
        username=user.username if user else None,
        role=user.role if user else None,
        permission=permission,
        min_level=min_level,
        min_role=min_role,
        sample_id=sample_id,
        extra=extra,
    )


@lru_cache(maxsize=1)
def _api_session_serializer() -> URLSafeTimedSerializer:
    """Api session serializer.

    Returns:
            The  api session serializer result.
    """
    return URLSafeTimedSerializer(
        secret_key=get_api_secret_key(runtime_app.config),
        salt=get_api_session_salt(runtime_app.config),
    )


def get_api_session_cookie_name() -> str:
    """Return api session cookie name.

    Returns:
        str: The function result.
    """
    return settings_session_cookie_name(runtime_app.config)


def get_api_session_ttl_seconds() -> int:
    """Return api session ttl seconds.

    Returns:
        int: The function result.
    """
    return settings_session_ttl_seconds(runtime_app.config)


def get_api_session_cookie_secure() -> bool:
    """Return api session cookie secure.

    Returns:
        bool: The function result.
    """
    return settings_session_cookie_secure(runtime_app.config)


def create_api_session_token(user_id: str) -> str:
    """Create api session token.

    Args:
        user_id (str): Value for ``user_id``.

    Returns:
        str: The function result.
    """
    return str(_api_session_serializer().dumps({"uid": str(user_id)}))


def _role_levels() -> dict[str, int]:
    """Role levels.

    Returns:
            The  role levels result.
    """
    return {
        role.get("role_id"): role.get("level", 0)
        for role in get_security_repository().get_all_roles()
        if role.get("role_id")
    }


def _api_user_from_doc(user_doc: dict) -> ApiUser:
    """Api user from doc.

    Args:
            user_doc: User doc.

    Returns:
            The  api user from doc result.
    """
    repo = get_security_repository()
    role_doc = repo.get_role(user_doc.get("role")) or {}
    asp_docs = repo.get_all_active_asps()
    user_model = UserModel.from_repository_payload(user_doc, role_doc, asp_docs)
    return ApiUser(
        id=str(user_model.id),
        email=user_model.email,
        fullname=user_model.fullname,
        username=user_model.username,
        role=user_model.role,
        access_level=user_model.access_level,
        permissions=list(user_model.permissions),
        denied_permissions=list(user_model.denied_permissions),
        assays=list(user_model.assays),
        assay_groups=list(user_model.assay_groups),
        envs=list(user_model.envs),
        asp_map=dict(user_model.asp_map),
        auth_type=str(getattr(user_model, "auth_type", "coyote3") or "coyote3"),
        must_change_password=bool(getattr(user_model, "must_change_password", False)),
    )


def serialize_api_user(user: ApiUser) -> dict:
    """Serialize api user.

    Args:
        user (ApiUser): Value for ``user``.

    Returns:
        dict: The function result.
    """
    return {
        "_id": user.id,
        "email": user.email,
        "fullname": user.fullname,
        "username": user.username,
        "role": user.role,
        "access_level": user.access_level,
        "permissions": sorted(user.permissions),
        "denied_permissions": sorted(user.denied_permissions),
        "assays": sorted(user.assays),
        "assay_groups": sorted(user.assay_groups),
        "envs": sorted(user.envs),
        "asp_map": user.asp_map,
        "auth_type": user.auth_type,
        "must_change_password": bool(user.must_change_password),
    }


def _extract_api_session_token(request: Request) -> str | None:
    """Extract api session token.

    Args:
            request: Request.

    Returns:
            The  extract api session token result.
    """
    auth_header = (request.headers.get("Authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        if token:
            return token
    return request.cookies.get(get_api_session_cookie_name())


def _decode_session_user(request: Request) -> ApiUser:
    """Decode session user.

    Args:
            request: Request.

    Returns:
            The  decode session user result.
    """
    api_token = _extract_api_session_token(request)
    if api_token:
        try:
            token_data = _api_session_serializer().loads(
                api_token,
                max_age=get_api_session_ttl_seconds(),
            )
        except SignatureExpired:
            raise _api_error(401, "Login required")
        except BadSignature:
            raise _api_error(401, "Login required")

        user_id = token_data.get("uid")
        if not user_id:
            raise _api_error(401, "Login required")

        user_doc = get_security_repository().get_user_by_id(str(user_id))
        if not user_doc or not user_doc.get("is_active", True):
            raise _api_error(401, "Login required")
        return _api_user_from_doc(user_doc)
    raise _api_error(401, "Login required")


def _enforce_access(
    user: ApiUser,
    permission: str | None = None,
    min_level: int | None = None,
    min_role: str | None = None,
) -> None:
    """Enforce access.

    Args:
            user: User.
            permission: Permission. Optional argument.
            min_level: Min level. Optional argument.
            min_role: Min role. Optional argument.

    Returns:
            None.
    """
    resolved_role_level = 0
    if min_role:
        resolved_role_level = _role_levels().get(min_role, 0)

    permission_ok = (
        permission is not None
        and permission in user.permissions
        and permission not in user.denied_permissions
    )
    level_ok = min_level is not None and user.access_level >= min_level
    role_ok = min_role is not None and user.access_level >= resolved_role_level

    if permission or min_level is not None or min_role:
        if not (permission_ok or level_ok or role_ok):
            raise _api_error(403, "Forbidden")


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


def require_access(
    permission: str | None = None,
    min_level: int | None = None,
    min_role: str | None = None,
):
    """Require access.

    Args:
        permission (str | None): Value for ``permission``.
        min_level (int | None): Value for ``min_level``.
        min_role (str | None): Value for ``min_role``.

    Returns:
        The function result.
    """

    def dep(request: Request) -> Generator[ApiUser, None, None]:
        """Dep.

        Args:
            request (Request): Value for ``request``.

        Returns:
            Generator[ApiUser, None, None]: The function result.
        """
        user: ApiUser | None = None
        try:
            user = _decode_session_user(request)
            _enforce_access(user, permission=permission, min_level=min_level, min_role=min_role)
        except HTTPException as exc:
            _audit_access_event(
                status="denied",
                reason=_http_exception_message(exc),
                request=request,
                user=user,
                permission=permission,
                min_level=min_level,
                min_role=min_role,
            )
            raise
        _audit_access_event(
            status="authorized",
            reason="Access granted",
            request=request,
            user=user,
            permission=permission,
            min_level=min_level,
            min_role=min_role,
        )
        token = set_current_user(user)
        try:
            yield user
        finally:
            reset_current_user(token)

    return dep


def _get_sample_for_api(sample_id: str, user: ApiUser, request: Request | None = None):
    """Get sample for api.

    Args:
            sample_id: Sample id.
            user: User.
            request: Request. Optional argument.

    Returns:
            The  get sample for api result.
    """
    repo = get_security_repository()
    sample = repo.get_sample(sample_id)
    if not sample:
        sample = repo.get_sample_by_id(sample_id)
    if not sample:
        _audit_access_event(
            status="denied",
            reason="Sample not found",
            request=request,
            user=user,
            sample_id=sample_id,
            extra={"check": "sample_lookup"},
        )
        raise _api_error(404, "Sample not found")

    sample_assay = sample.get("assay", "")
    if sample_assay not in set(user.assays or []):
        _audit_access_event(
            status="denied",
            reason="Forbidden",
            request=request,
            user=user,
            sample_id=sample_id,
            extra={"sample_assay": sample_assay},
        )
        raise _api_error(403, "Forbidden")
    return sample


def _require_internal_token(request: Request) -> None:
    """Require internal token.

    Args:
            request: Request.

    Returns:
            None.
    """
    try:
        expected = get_internal_api_token(runtime_app.config)
    except RuntimeError:
        expected = ""
    provided = request.headers.get("X-Coyote-Internal-Token")
    if not expected or not provided or provided != expected:
        raise _api_error(403, "Forbidden")
