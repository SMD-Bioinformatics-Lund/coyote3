"""Shared HTTP-layer helpers for the API."""

from __future__ import annotations

from copy import deepcopy

from fastapi import HTTPException

from api.contracts.managed_resources import aspc_spec_for_category
from api.contracts.managed_ui_schemas import build_form_spec
from api.extensions import store, util


def api_error(status_code: int, message: str) -> HTTPException:
    """Build a standardized API HTTP exception payload.

    Args:
        status_code: HTTP status code to expose to the client.
        message: Human-readable error summary.

    Returns:
        A ``fastapi.HTTPException`` with the standard API error body.
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
    assay_config = store.assay_configuration_handler.get_aspc_no_meta(
        str(sample.get("assay") or ""),
        str(sample.get("profile", "production") or "production"),
    )
    if not assay_config:
        return None
    omics = str(sample.get("omics_layer") or "").upper()
    if not omics:
        omics = "RNA" if sample.get("fusion_files") else "DNA"
    assay_config_schema = build_form_spec(aspc_spec_for_category(omics))
    return util.common.format_assay_config(deepcopy(assay_config), assay_config_schema)
