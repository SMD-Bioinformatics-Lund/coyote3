"""Authoritative FastAPI application for Coyote3."""

from __future__ import annotations

import os
from dataclasses import replace

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.app.documentation import API_DESCRIPTION, register_api_documentation
from api.app.http import api_error, get_formatted_assay_config
from api.app.lifecycle import create_lifespan, register_route_modules
from api.app.middleware import build_authentication_middleware, build_security_headers_middleware
from api.app.openapi import SAMPLE_INGEST_PATHS, apply_openapi_security_schema
from api.app.runtime_state import app as runtime_app
from api.config import configure_process_env, get_runtime_mode_flags
from api.config.runtime_settings import DefaultConfig
from api.config.security import get_runtime_environment
from api.contracts.http import ApiValidationIssue
from api.domain.core.exceptions import AppError
from api.infra.observability.logging import (
    bind_request_context,
    request_context_from_request,
    reset_request_context,
)
from api.interfaces.http.errors import error_response
from api.interfaces.http.registry import ROUTERS, auth_http_exception_handler
from api.interfaces.http.tags import OPENAPI_TAGS


def _api_error(status_code: int, message: str) -> AppError:
    """Build a standardized application error."""
    return api_error(status_code, message)


def _get_formatted_assay_config(sample: dict):
    """Resolve assay configuration for a sample payload."""
    return get_formatted_assay_config(sample)


def _script_name() -> str:
    """Return the externally mounted application prefix."""
    return str(DefaultConfig.SCRIPT_NAME)


async def unhandled_exception_handler(request: Request, exc: Exception):
    """Return a consistent JSON payload for unexpected API failures."""
    response = error_response(request, 500)
    runtime_app.logger.exception(
        "Unhandled API exception on %s %s",
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
        extra={"request_id": getattr(request.state, "request_id", None)},
    )
    from api.app.deps.services import get_audit_service

    context_token = bind_request_context(
        replace(request_context_from_request(request), request_id=request.state.request_id)
    )
    try:
        audit = get_audit_service()
        if audit is not None:
            audit.record(
                "api.exception.unhandled",
                "Unhandled API exception",
                severity="error",
                category="runtime",
                outcome="failure",
                actor=getattr(request.state, "authenticated_user", None),
                resource_type="api_route",
                resource_id=str(request.url.path),
                tags=["api", "exception"],
                metadata={
                    "method": request.method,
                    "exception_type": type(exc).__name__,
                    "request_id": getattr(request.state, "request_id", None),
                },
            )
    except Exception:
        runtime_app.logger.critical(
            "Unable to audit unhandled API exception",
            exc_info=True,
            extra={"request_id": request.state.request_id},
        )
    finally:
        reset_request_context(context_token)
    return response


async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    """Translate FastAPI validation errors into the API error contract.

    Args:
        _request: Incoming request that failed validation.
        exc: Validation error raised by FastAPI.

    Returns:
        JSONResponse: Normalized 422 response payload.
    """
    issues = []
    for err in exc.errors():
        location = ".".join(str(item) for item in err.get("loc", []) if item != "body")
        issues.append(
            ApiValidationIssue(
                field=location or "body", message=err.get("msg", "Invalid value")
            ).model_dump()
        )
    from api.app.deps.services import get_audit_service

    audit = get_audit_service()
    if audit is not None:
        audit.record(
            "api.validation.failed",
            "API request validation failed",
            severity="warning",
            category="runtime",
            outcome="failure",
            actor=getattr(_request.state, "authenticated_user", None),
            resource_type="api_route",
            resource_id=str(_request.url.path),
            tags=["api", "validation"],
            metadata={"details": issues},
        )
    return error_response(_request, 422, "Validation failed", details=issues)


async def app_error_handler(_request: Request, exc: AppError):
    """Translate domain application errors into the public API error contract."""
    if exc.status_code >= 500:
        runtime_app.logger.error(
            "Application service failure: %s",
            exc.message,
            extra={"request_id": getattr(_request.state, "request_id", None)},
        )
    return error_response(
        _request,
        int(exc.status_code or 500),
        exc.message,
        details=exc.details,
        category=exc.category,
        hint=exc.hint,
    )


def create_api_app() -> FastAPI:
    """Build and return the canonical FastAPI application instance."""
    configure_process_env()
    mode_flags = get_runtime_mode_flags()
    script_name = _script_name()
    default_environment = (
        "test"
        if mode_flags["testing"]
        else "development"
        if mode_flags["development"]
        else "production"
    )
    environment = get_runtime_environment({"ENV_NAME": os.getenv("ENV_NAME", default_environment)})
    description = API_DESCRIPTION
    if environment not in {"production", "prod"}:
        description = (
            f"> **WARNING: {environment.upper()} environment.** "
            "Not for production clinical use.\n\n" + description
        )

    from api import version

    app = FastAPI(
        title="Coyote3 API",
        description=description,
        version=version.environment_version(environment),
        root_path=script_name,
        root_path_in_servers=bool(script_name),
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/v1/openapi.json",
        openapi_tags=OPENAPI_TAGS,
        servers=[{"url": script_name or "/"}],
        lifespan=create_lifespan(
            testing=mode_flags["testing"],
            development=mode_flags["development"],
        ),
    )

    app.add_exception_handler(HTTPException, auth_http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, auth_http_exception_handler)
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.middleware("http")(
        build_authentication_middleware(
            testing=mode_flags["testing"],
            development=mode_flags["development"],
        )
    )
    app.middleware("http")(build_security_headers_middleware())
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.openapi = lambda: apply_openapi_security_schema(app)
    register_api_documentation(app, environment=environment)
    for registration in ROUTERS:
        selected = SAMPLE_INGEST_PATHS | {"/api/v1/health"}
        has_selected = any(
            getattr(route, "path", "") in selected for route in registration.router.routes
        )
        if has_selected:
            for route in registration.router.routes:
                route.include_in_schema = getattr(route, "path", "") in selected
                if route.include_in_schema:
                    route.tags = ["Sample ingestion"]
        app.include_router(
            registration.router,
            include_in_schema=registration.include_in_schema or has_selected,
        )
    register_route_modules()
    return app


app = create_api_app()
