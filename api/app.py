"""FastAPI application for Coyote3 API v1."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import os

from fastapi import FastAPI, HTTPException, Request
from flask.sessions import SecureCookieSessionInterface
from itsdangerous import BadSignature

from coyote import init_app
from coyote.extensions import store, util
from coyote.models.user import UserModel


os.environ.setdefault("REQUIRE_EXTERNAL_API", "0")
flask_app = init_app(
    testing=bool(int(os.getenv("TESTING", "0"))),
    development=bool(int(os.getenv("DEVELOPMENT", "0"))),
)
_session_interface = SecureCookieSessionInterface()
_session_serializer = _session_interface.get_signing_serializer(flask_app)

app = FastAPI(
    title="Coyote3 API",
    version="1.0.0",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
)


def create_api_app():
    """Return the canonical FastAPI application instance."""
    return app


@dataclass
class ApiUser:
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
    expected = flask_app.config.get("INTERNAL_API_TOKEN") or flask_app.config.get("SECRET_KEY")
    provided = request.headers.get("X-Coyote-Internal-Token")
    if not expected or not provided or provided != expected:
        raise _api_error(403, "Forbidden")


def _to_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


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


def _decode_session_user(request: Request) -> ApiUser:
    cookie_name = flask_app.config.get("SESSION_COOKIE_NAME", "session")
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

    role_doc = store.roles_handler.get_role(user_doc.get("role")) or {}
    asp_docs = store.asp_handler.get_all_asps(is_active=True)
    user_model = UserModel.from_mongo(user_doc, role_doc, asp_docs)

    return ApiUser(
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
    def dep(request: Request) -> ApiUser:
        user = _decode_session_user(request)
        _enforce_access(user, permission=permission, min_level=min_level, min_role=min_role)
        return user

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
