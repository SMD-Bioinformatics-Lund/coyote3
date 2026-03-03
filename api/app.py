"""FastAPI application for Coyote3 API v1."""

from __future__ import annotations

from copy import deepcopy

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from api.extensions import store, util
from api.runtime_bootstrap import create_runtime_context
from api.runtime import app as runtime_app
from api.runtime import bind_runtime_context
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


def _api_error(status_code: int, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"status": status_code, "error": message})


def _get_formatted_assay_config(sample: dict):
    assay_config = store.aspc_handler.get_aspc_no_meta(
        sample.get("assay"), sample.get("profile", "production")
    )
    if not assay_config:
        return None
    schema_name = assay_config.get("schema_name")
    assay_config_schema = store.schema_handler.get_schema(schema_name)
    return util.common.format_assay_config(deepcopy(assay_config), assay_config_schema)


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
