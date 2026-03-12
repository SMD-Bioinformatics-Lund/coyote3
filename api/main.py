"""Authoritative FastAPI application for Coyote3."""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.config import configure_process_env, get_runtime_mode_flags
from api.contracts.http import ApiValidationIssue
from api.http import api_error, get_formatted_assay_config
from api.lifecycle import create_lifespan, register_route_modules
from api.middleware import build_authentication_middleware
from api.openapi import apply_openapi_security_schema
from api.routers.registry import ROUTERS, auth_http_exception_handler
from api.runtime import app as runtime_app

def _api_error(status_code: int, message: str) -> HTTPException:
    return api_error(status_code, message)


def _get_formatted_assay_config(sample: dict):
    return get_formatted_assay_config(sample)


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


async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    issues = []
    for err in exc.errors():
        location = ".".join(str(item) for item in err.get("loc", []) if item != "body")
        issues.append(ApiValidationIssue(field=location or "body", message=err.get("msg", "Invalid value")).model_dump())
    return JSONResponse(
        status_code=422,
        content={
            "status": 422,
            "error": "Validation failed",
            "details": issues,
        },
    )

def create_api_app() -> FastAPI:
    """Build and return the canonical FastAPI application instance."""
    configure_process_env()
    mode_flags = get_runtime_mode_flags()

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

    app.add_exception_handler(HTTPException, auth_http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.middleware("http")(
        build_authentication_middleware(
            testing=mode_flags["testing"],
            development=mode_flags["development"],
        )
    )
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.openapi = lambda: apply_openapi_security_schema(app)
    for router in ROUTERS:
        app.include_router(router)
    register_route_modules()
    return app


app = create_api_app()

# Export a stable runtime string for external launchers and docs.
APP_IMPORT_PATH = os.getenv("COYOTE3_API_APP", "api.main:app")
