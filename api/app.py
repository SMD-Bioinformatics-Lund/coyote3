"""FastAPI application for Coyote3 API v1."""

from __future__ import annotations

import time
import threading
import uuid
import os
from contextlib import asynccontextmanager
from importlib import import_module
from copy import deepcopy

from fastapi import FastAPI, HTTPException, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from api.audit.access_events import emit_mutation_event, emit_request_event, request_ip
from api.extensions import store, util
from api.runtime import app as runtime_app
from api.runtime import (
    bind_runtime_context,
    current_username,
    reset_current_user,
    reset_current_request_id,
    set_current_user,
    set_current_request_id,
)
from api.runtime_bootstrap import create_runtime_context
from api.security.access import (
    get_api_session_cookie_name,
    is_public_api_path,
    resolve_request_user,
)
from api.settings import configure_process_env, get_runtime_mode_flags

configure_process_env()
mode_flags = get_runtime_mode_flags()
util.init_util()

_runtime_bootstrap_lock = threading.Lock()
_runtime_initialized = False


def ensure_runtime_initialized() -> None:
    """Initialize API runtime dependencies once, lazily."""
    global _runtime_initialized
    if _runtime_initialized:
        return
    with _runtime_bootstrap_lock:
        if _runtime_initialized:
            return
        store_state_before = dict(store.__dict__)
        try:
            runtime_context = create_runtime_context(
                testing=mode_flags["testing"],
                development=mode_flags["development"],
            )
            bind_runtime_context(runtime_context)
        except Exception:
            if os.environ.get("PYTEST_CURRENT_TEST"):
                store.__dict__.clear()
                store.__dict__.update(store_state_before)
                runtime_app.logger.warning(
                    "Skipping runtime DB bootstrap during pytest due to initialization failure.",
                    exc_info=True,
                )
            else:
                raise
        _runtime_initialized = True

@asynccontextmanager
async def _lifespan(_app: FastAPI):
    ensure_runtime_initialized()
    yield


app = FastAPI(
    title="Coyote3 API",
    version="1.0.0",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
    lifespan=_lifespan,
)

_PROTECTED_OPENAPI_EXACT = {
    "/api/v1/auth/me",
    "/api/v1/auth/whoami",
}


@app.middleware("http")
async def api_authentication_middleware(request: Request, call_next):
    ensure_runtime_initialized()
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


_ROUTE_MODULES = (
    "api.routes.admin",
    "api.routes.common",
    "api.routes.coverage",
    "api.routes.dashboard",
    "api.routes.dna",
    "api.routes.dna_structural",
    "api.routes.home",
    "api.routes.internal",
    "api.routes.public",
    "api.routes.reports",
    "api.routes.rna",
    "api.routes.rna_mutations",
    "api.routes.samples",
    "api.routes.system",
)


def _register_route_modules() -> None:
    """Import route modules for side-effect registration with FastAPI."""
    for module_path in _ROUTE_MODULES:
        import_module(module_path)


_register_route_modules()
