"""Authoritative FastAPI application for Coyote3."""

from __future__ import annotations

import os
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from api.audit.access_events import emit_mutation_event, emit_request_event, request_ip
from api.config import configure_process_env, get_runtime_mode_flags
from api.extensions import store, util
from api.http import api_error, get_formatted_assay_config
from api.lifecycle import create_lifespan, ensure_runtime_initialized, register_route_modules
from api.routers.registry import ROUTERS, auth_http_exception_handler
from api.runtime import (
    app as runtime_app,
    current_username,
    reset_current_request_id,
    reset_current_user,
    set_current_request_id,
    set_current_user,
)
from api.security.access import (
    get_api_session_cookie_name,
    is_public_api_path,
    resolve_request_user,
)

configure_process_env()
mode_flags = get_runtime_mode_flags()
util.init_util()


def _api_error(status_code: int, message: str) -> HTTPException:
    return api_error(status_code, message)


def _get_formatted_assay_config(sample: dict):
    return get_formatted_assay_config(sample)


app = FastAPI(
    title="Coyote3 API",
    version="1.0.0",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
    lifespan=create_lifespan(
        testing=mode_flags["testing"],
        development=mode_flags["development"],
    ),
)

_PROTECTED_OPENAPI_EXACT = {
    "/api/v1/auth/me",
    "/api/v1/auth/whoami",
}

app.add_exception_handler(HTTPException, auth_http_exception_handler)


@app.middleware("http")
async def api_authentication_middleware(request: Request, call_next):
    ensure_runtime_initialized(
        testing=mode_flags["testing"],
        development=mode_flags["development"],
    )
    start = time.perf_counter()
    path = request.url.path
    authenticated_user = None
    user_token = None
    request_id = (request.headers.get("X-Request-ID") or "").strip() or str(uuid.uuid4())
    request.state.request_id = request_id
    request_token = set_current_request_id(request_id)
    response: JSONResponse | None = None
    if path.startswith("/api/v1/"):
        authenticated_user = resolve_request_user(request)
        if authenticated_user is not None:
            request.state.authenticated_user = authenticated_user
            user_token = set_current_user(authenticated_user)
        if not is_public_api_path(path) and authenticated_user is None:
            exc = HTTPException(status_code=401, detail={"status": 401, "error": "Login required"})
            payload = (
                exc.detail
                if isinstance(exc.detail, dict)
                else {"status": exc.status_code, "error": str(exc.detail)}
            )
            response = JSONResponse(status_code=exc.status_code, content=payload)
            response.headers["X-Request-ID"] = request_id
            runtime_app.logger.info(
                (
                    "api_request request_id=%s method=%s path=%s status=%s "
                    "duration_ms=%.2f user=%s ip=%s"
                ),
                request_id,
                request.method,
                path,
                exc.status_code,
                (time.perf_counter() - start) * 1000.0,
                "anonymous",
                request_ip(request),
            )
            emit_request_event(
                request=request,
                username="anonymous",
                status_code=exc.status_code,
                duration_ms=(time.perf_counter() - start) * 1000.0,
                extra={"kind": "authentication"},
            )
            if user_token is not None:
                reset_current_user(user_token)
            reset_current_request_id(request_token)
            return response
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    duration_ms = (time.perf_counter() - start) * 1000.0
    username = (
        authenticated_user.username
        if authenticated_user is not None
        else current_username(default="anonymous")
    )
    runtime_app.logger.info(
        "api_request request_id=%s method=%s path=%s status=%s duration_ms=%.2f user=%s ip=%s",
        request_id,
        request.method,
        path,
        response.status_code,
        duration_ms,
        username,
        request_ip(request),
    )
    if path.startswith("/api/v1/"):
        emit_request_event(
            request=request,
            username=username,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
    if (
        path.startswith("/api/v1/")
        and request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}
        and not is_public_api_path(path)
    ):
        emit_mutation_event(
            request=request,
            username=username,
            status_code=response.status_code,
            action=request.method.upper(),
            target=path,
        )
    if user_token is not None:
        reset_current_user(user_token)
    reset_current_request_id(request_token)
    return response


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


app.add_exception_handler(Exception, unhandled_exception_handler)


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
for router in ROUTERS:
    app.include_router(router)
register_route_modules()

# Export a stable runtime string for external launchers and docs.
APP_IMPORT_PATH = os.getenv("COYOTE3_API_APP", "api.main:app")
