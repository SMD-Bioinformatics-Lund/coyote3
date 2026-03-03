"""Authentication and access control helpers for API routes."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
import json
import logging

from fastapi import HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from api.domain.models.user import UserModel
from api.extensions import store
from api.runtime import app as runtime_app
from api.runtime import reset_current_user, set_current_user

_audit_logger = logging.getLogger("audit")


@dataclass
class ApiUser:
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


def _api_error(status_code: int, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"status": status_code, "error": message})


def _http_exception_message(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, dict):
        return str(detail.get("error") or detail.get("details") or detail)
    return str(detail)


def _to_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _request_ip(request: Request | None) -> str:
    if request is None:
        return "N/A"
    forwarded_for = (request.headers.get("X-Forwarded-For") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or "N/A"
    if request.client and request.client.host:
        return str(request.client.host)
    return "N/A"


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
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "api",
        "action": "access_check",
        "status": status,
        "reason": reason,
        "method": request.method if request else None,
        "path": str(request.url.path) if request else None,
        "ip": _request_ip(request),
        "user_id": user.id if user else None,
        "username": user.username if user else None,
        "role": user.role if user else None,
        "sample_id": str(sample_id) if sample_id is not None else None,
        "required": {
            "permission": permission,
            "min_level": min_level,
            "min_role": min_role,
        },
        "extra": extra or {},
    }
    payload = json.dumps(event, default=str)
    if status == "denied":
        _audit_logger.warning(payload)
    else:
        _audit_logger.info(payload)


@lru_cache(maxsize=1)
def _api_session_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        secret_key=str(runtime_app.config.get("SECRET_KEY") or "coyote3-api"),
        salt=str(runtime_app.config.get("API_SESSION_SALT", "coyote3-api-session-v1")),
    )


def get_api_session_cookie_name() -> str:
    return str(runtime_app.config.get("API_SESSION_COOKIE_NAME") or "coyote3_api_session")


def get_api_session_ttl_seconds() -> int:
    value = runtime_app.config.get("API_SESSION_TTL_SECONDS", 12 * 60 * 60)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 12 * 60 * 60


def get_api_session_cookie_secure() -> bool:
    return _to_bool(runtime_app.config.get("SESSION_COOKIE_SECURE"), default=False)


def create_api_session_token(user_id: str) -> str:
    return str(_api_session_serializer().dumps({"uid": str(user_id)}))


def _role_levels() -> dict[str, int]:
    return {role["_id"]: role.get("level", 0) for role in store.roles_handler.get_all_roles()}


def _api_user_from_doc(user_doc: dict) -> ApiUser:
    role_doc = store.roles_handler.get_role(user_doc.get("role")) or {}
    asp_docs = store.asp_handler.get_all_asps(is_active=True)
    user_model = UserModel.from_mongo(user_doc, role_doc, asp_docs)
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
    )


def serialize_api_user(user: ApiUser) -> dict:
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
    }


def _extract_api_session_token(request: Request) -> str | None:
    auth_header = (request.headers.get("Authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        if token:
            return token
    return request.cookies.get(get_api_session_cookie_name())


def _decode_session_user(request: Request) -> ApiUser:
    api_token = _extract_api_session_token(request)
    if api_token:
        try:
            token_data = _api_session_serializer().loads(
                api_token,
                max_age=get_api_session_ttl_seconds(),
            )
        except SignatureExpired:
            raise _api_error(401, "Session expired")
        except BadSignature:
            raise _api_error(401, "Login required")

        user_id = token_data.get("uid")
        if not user_id:
            raise _api_error(401, "Login required")

        user_doc = store.user_handler.user_with_id(str(user_id))
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
            raise _api_error(403, "You do not have access to this page.")


def require_access(
    permission: str | None = None,
    min_level: int | None = None,
    min_role: str | None = None,
):
    def dep(request: Request) -> Generator[ApiUser, None, None]:
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
    sample = store.sample_handler.get_sample(sample_id)
    if not sample:
        sample = store.sample_handler.get_sample_by_id(sample_id)
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
            reason="Access denied: sample assay mismatch",
            request=request,
            user=user,
            sample_id=sample_id,
            extra={"sample_assay": sample_assay},
        )
        raise _api_error(403, "Access denied: sample assay mismatch")
    return sample


def _require_internal_token(request: Request) -> None:
    expected = runtime_app.config.get("INTERNAL_API_TOKEN") or runtime_app.config.get("SECRET_KEY")
    provided = request.headers.get("X-Coyote-Internal-Token")
    if not expected or not provided or provided != expected:
        raise _api_error(403, "Forbidden")
