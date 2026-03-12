"""Compatibility shim for legacy imports.

The authoritative FastAPI application now lives in ``api.main``.
"""

from api.audit.access_events import emit_mutation_event, emit_request_event
from api.main import APP_IMPORT_PATH, _api_error, _get_formatted_assay_config, app, create_api_app

__all__ = [
    "APP_IMPORT_PATH",
    "app",
    "create_api_app",
    "_api_error",
    "_get_formatted_assay_config",
    "emit_mutation_event",
    "emit_request_event",
]
