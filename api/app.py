"""FastAPI application for Coyote3 API v1."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import os
from collections.abc import Generator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from flask.sessions import SecureCookieSessionInterface
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

# API runtime must never depend on an external API health check.
os.environ["REQUIRE_EXTERNAL_API"] = "0"

from api.extensions import store, util
from api.runtime_bootstrap import create_runtime_context
from api.models.user import UserModel
from api.runtime import app as runtime_app
from api.runtime import bind_runtime_context, reset_current_user, set_current_user

runtime_context = create_runtime_context(
    testing=bool(int(os.getenv("TESTING", "0"))),
    development=bool(int(os.getenv("DEVELOPMENT", "0"))),
)
bind_runtime_context(runtime_context)
_session_interface = SecureCookieSessionInterface()
_session_serializer = _session_interface.get_signing_serializer(runtime_context)
_api_session_serializer = URLSafeTimedSerializer(
    secret_key=str(runtime_context.secret_key or runtime_app.config.get("SECRET_KEY") or "coyote3-api"),
    salt=str(runtime_app.config.get("API_SESSION_SALT", "coyote3-api-session-v1")),
)

app = FastAPI(
    title="Coyote3 API",
    version="1.0.0",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Return a consistent JSON payload for unexpected API failures."""
    runtime_app.logger.exception("Unhandled API exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "status": 500,
            "error": "Internal server error",
            "details": "Unexpected API failure",
        },
    )


def create_api_app():
    """Return the canonical FastAPI application instance."""
    return app


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


def _require_internal_token(request: Request) -> None:
    expected = runtime_app.config.get("INTERNAL_API_TOKEN") or runtime_app.config.get("SECRET_KEY")
    provided = request.headers.get("X-Coyote-Internal-Token")
    if not expected or not provided or provided != expected:
        raise _api_error(403, "Forbidden")


def _to_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


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
    return str(_api_session_serializer.dumps({"uid": str(user_id)}))


def _role_levels() -> dict[str, int]:
    return {role["_id"]: role.get("level", 0) for role in store.roles_handler.get_all_roles()}


def _get_formatted_assay_config(sample: dict):
    assay_config = store.aspc_handler.get_aspc_no_meta(
        sample.get("assay"), sample.get("profile", "production")
    )
    if not assay_config:
        return None
    schema_name = assay_config.get("schema_name")
    assay_config_schema = store.schema_handler.get_schema(schema_name)
    return util.common.format_assay_config(deepcopy(assay_config), assay_config_schema)


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


def _decode_legacy_flask_session_user(request: Request) -> ApiUser:
    cookie_name = runtime_app.config.get("SESSION_COOKIE_NAME", "session")
    cookie_val = request.cookies.get(cookie_name)
    if not cookie_val or _session_serializer is None:
        raise _api_error(401, "Login required")

    try:
        session_data = _session_serializer.loads(cookie_val)
    except BadSignature:
        raise _api_error(401, "Login required")

    user_id = session_data.get("_user_id")
    if not user_id:
        raise _api_error(401, "Login required")

    user_doc = store.user_handler.user_with_id(user_id)
    if not user_doc:
        raise _api_error(401, "Login required")
    return _api_user_from_doc(user_doc)


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
            token_data = _api_session_serializer.loads(
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

    # Backward-compatible fallback while Flask session migration completes.
    return _decode_legacy_flask_session_user(request)


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
        user = _decode_session_user(request)
        _enforce_access(user, permission=permission, min_level=min_level, min_role=min_role)
        token = set_current_user(user)
        try:
            yield user
        finally:
            reset_current_user(token)

    return dep


def _get_sample_for_api(sample_id: str, user: ApiUser):
    sample = store.sample_handler.get_sample(sample_id)
    if not sample:
        sample = store.sample_handler.get_sample_by_id(sample_id)
    if not sample:
        raise _api_error(404, "Sample not found")

    sample_assay = sample.get("assay", "")
    if sample_assay not in set(user.assays or []):
        raise _api_error(403, "Access denied: sample assay mismatch")
    return sample


from api.routes import system as _system_routes  # noqa: F401


from api.routes import samples as _sample_routes  # noqa: F401
from api.routes import internal as _internal_routes  # noqa: F401
from api.routes import admin as _admin_routes  # noqa: F401

from api.routes import dna as _dna_routes  # noqa: F401
from api.routes import rna as _rna_routes  # noqa: F401
from api.routes import reports as _report_routes  # noqa: F401
from api.routes import dashboard as _dashboard_routes  # noqa: F401
from api.routes import common as _common_routes  # noqa: F401
from api.routes import coverage as _coverage_routes  # noqa: F401
from api.routes import home as _home_routes  # noqa: F401
from api.routes import public as _public_routes  # noqa: F401
