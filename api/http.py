"""Shared HTTP-layer helpers for the API."""

from __future__ import annotations

from copy import deepcopy

from fastapi import HTTPException

from api.extensions import store, util


def api_error(status_code: int, message: str) -> HTTPException:
    """Build a standardized API HTTP exception payload.

    Args:
        status_code: HTTP status code to expose to the client.
        message: Human-readable error summary.

    Returns:
        A ``fastapi.HTTPException`` with the repository-standard error body.
    """
    return HTTPException(
        status_code=status_code,
        detail={"status": status_code, "error": message, "details": None},
    )


def get_formatted_assay_config(sample: dict):
    """Resolve and format the assay configuration for a sample document.

    Args:
        sample: Sample document containing assay and profile metadata.

    Returns:
        The formatted assay configuration payload, or ``None`` when no assay
        configuration is available for the sample.
    """
    assay_config = store.aspc_handler.get_aspc_no_meta(
        sample.get("assay"), sample.get("profile", "production")
    )
    if not assay_config:
        return None
    schema_name = assay_config.get("schema_name")
    assay_config_schema = store.schema_handler.get_schema(schema_name)
    return util.common.format_assay_config(deepcopy(assay_config), assay_config_schema)
