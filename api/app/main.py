"""Authoritative FastAPI application for Coyote3."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.app.http import api_error, get_formatted_assay_config
from api.app.lifecycle import create_lifespan, register_route_modules
from api.app.middleware import build_authentication_middleware
from api.app.openapi import apply_openapi_security_schema
from api.app.runtime_state import app as runtime_app
from api.config import configure_process_env, get_runtime_mode_flags
from api.config.runtime_settings import DefaultConfig
from api.contracts.http import ApiValidationIssue
from api.domain.core.exceptions import AppError
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
    runtime_app.logger.exception(
        "Unhandled API exception on %s %s", request.method, request.url.path
    )
    from api.app.deps.services import get_audit_service

    audit = get_audit_service()
    if audit is not None:
        audit.record(
            "api.exception.unhandled",
            "Unhandled API exception",
            severity="error",
            category="runtime",
            outcome="failure",
            actor="anonymous",
            resource_type="api_route",
            resource_id=str(request.url.path),
            tags=["api", "exception"],
            metadata={"method": request.method, "details": str(exc)},
        )
    return JSONResponse(
        status_code=500,
        content={
            "status": 500,
            "error": "Internal server error",
            "details": "Unexpected API failure",
        },
    )


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
            actor="anonymous",
            resource_type="api_route",
            tags=["api", "validation"],
            metadata={"details": issues},
        )
    return JSONResponse(
        status_code=422,
        content={
            "status": 422,
            "error": "Validation failed",
            "details": issues,
        },
    )


async def app_error_handler(_request: Request, exc: AppError):
    """Translate domain application errors into the public API error contract."""
    return JSONResponse(
        status_code=int(exc.status_code or 500),
        content={
            "status": int(exc.status_code or 500),
            "error": exc.message,
            "details": exc.details,
            "category": exc.category,
            "hint": exc.hint,
        },
    )


def create_api_app() -> FastAPI:
    """Build and return the canonical FastAPI application instance."""
    configure_process_env()
    mode_flags = get_runtime_mode_flags()
    script_name = _script_name()

    app = FastAPI(
        title="Coyote3 API",
        version="1.0.0",
        root_path=script_name,
        root_path_in_servers=bool(script_name),
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json",
        openapi_tags=OPENAPI_TAGS,
        lifespan=create_lifespan(
            testing=mode_flags["testing"],
            development=mode_flags["development"],
        ),
    )

    app.add_exception_handler(HTTPException, auth_http_exception_handler)
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.middleware("http")(
        build_authentication_middleware(
            testing=mode_flags["testing"],
            development=mode_flags["development"],
        )
    )
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.openapi = lambda: apply_openapi_security_schema(app)
    for registration in ROUTERS:
        app.include_router(
            registration.router,
            include_in_schema=registration.include_in_schema,
        )
    register_route_modules()
    return app


app = create_api_app()
