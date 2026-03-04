"""FastAPI application for Coyote3 API v1."""

from __future__ import annotations

from copy import deepcopy

from fastapi import FastAPI, HTTPException, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from api.extensions import store, util
from api.runtime import app as runtime_app
from api.runtime import bind_runtime_context
from api.runtime_bootstrap import create_runtime_context
from api.security.access import (
    get_api_session_cookie_name,
    is_public_api_path,
    require_authenticated,
)
from api.settings import configure_process_env, get_runtime_mode_flags

configure_process_env()
mode_flags = get_runtime_mode_flags()
runtime_context = create_runtime_context(
    testing=mode_flags["testing"],
    development=mode_flags["development"],
)
bind_runtime_context(runtime_context)

app = FastAPI(
    title="Coyote3 API",
    version="1.0.0",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
)

_PROTECTED_OPENAPI_EXACT = {
    "/api/v1/auth/me",
    "/api/v1/auth/whoami",
}


@app.middleware("http")
async def api_authentication_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/v1/") and not is_public_api_path(path):
        try:
            require_authenticated(request)
        except HTTPException as exc:
            payload = (
                exc.detail
                if isinstance(exc.detail, dict)
                else {"status": exc.status_code, "error": str(exc.detail)}
            )
            return JSONResponse(status_code=exc.status_code, content=payload)
    return await call_next(request)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Return a consistent JSON payload for unexpected API failures."""
    runtime_app.logger.exception(
        "Unhandled API exception on %s %s", request.method, request.url.path
    )
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


def _apply_openapi_security_schema() -> dict:
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description="Coyote3 API",
        routes=app.routes,
    )
    components = schema.setdefault("components", {})
    security_schemes = components.setdefault("securitySchemes", {})
    security_schemes["ApiSessionCookie"] = {
        "type": "apiKey",
        "in": "cookie",
        "name": get_api_session_cookie_name(),
    }
    security_schemes["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "opaque",
    }

    for path, operations in schema.get("paths", {}).items():
        for method, operation in operations.items():
            if method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                continue
            if path.startswith("/api/v1/") and (
                not is_public_api_path(path) or path in _PROTECTED_OPENAPI_EXACT
            ):
                operation["security"] = [{"ApiSessionCookie": []}, {"BearerAuth": []}]
                responses = operation.setdefault("responses", {})
                responses.setdefault("401", {"description": "Unauthorized"})
                responses.setdefault("403", {"description": "Forbidden"})

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = _apply_openapi_security_schema


def _api_error(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"status": status_code, "error": message},
    )


def _get_formatted_assay_config(sample: dict):
    assay_config = store.aspc_handler.get_aspc_no_meta(
        sample.get("assay"), sample.get("profile", "production")
    )
    if not assay_config:
        return None
    schema_name = assay_config.get("schema_name")
    assay_config_schema = store.schema_handler.get_schema(schema_name)
    return util.common.format_assay_config(deepcopy(assay_config), assay_config_schema)


from api.routes import admin as _admin_routes  # noqa: E402,F401
from api.routes import common as _common_routes  # noqa: E402,F401
from api.routes import coverage as _coverage_routes  # noqa: E402,F401
from api.routes import dashboard as _dashboard_routes  # noqa: E402,F401
from api.routes import dna as _dna_routes  # noqa: E402,F401
from api.routes import home as _home_routes  # noqa: E402,F401
from api.routes import internal as _internal_routes  # noqa: E402,F401
from api.routes import public as _public_routes  # noqa: E402,F401
from api.routes import reports as _report_routes  # noqa: E402,F401
from api.routes import rna as _rna_routes  # noqa: E402,F401
from api.routes import samples as _sample_routes  # noqa: E402,F401
from api.routes import system as _system_routes  # noqa: E402,F401
