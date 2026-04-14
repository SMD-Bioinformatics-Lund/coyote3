"""Shared HTTP-layer helpers for the API."""

from __future__ import annotations

from copy import deepcopy

from fastapi import HTTPException

from api.contracts.managed_resources import aspc_spec_for_category
from api.contracts.managed_ui_schemas import build_form_spec
from api.extensions import store, util


def api_error(
    status_code: int,
    message: str,
    details: str | None = None,
    *,
    category: str | None = None,
    hint: str | None = None,
) -> HTTPException:
    """Build a standardized API HTTP exception payload.

    Args:
        status_code: HTTP status code to expose to the client.
        message: Human-readable error summary.

    Returns:
        A ``fastapi.HTTPException`` with the standard API error body.
    """
    return HTTPException(
        status_code=status_code,
        detail={
            "status": status_code,
            "error": message,
            "details": details,
            "category": category,
            "hint": hint,
        },
    )


def validation_error(message: str, details: str | None = None, *, hint: str | None = None):
    """Build a standardized validation HTTP error."""
    return api_error(400, message, details, category="validation", hint=hint)


def not_found_error(message: str, details: str | None = None, *, hint: str | None = None):
    """Build a standardized not-found HTTP error."""
    return api_error(404, message, details, category="not_found", hint=hint)


def forbidden_error(message: str, details: str | None = None, *, hint: str | None = None):
    """Build a standardized forbidden HTTP error."""
    return api_error(403, message, details, category="scope", hint=hint)


def setup_error(
    message: str,
    details: str | None = None,
    *,
    hint: str | None = None,
    status_code: int = 422,
):
    """Build a standardized system/setup HTTP error."""
    return api_error(status_code, message, details, category="setup", hint=hint)


def get_formatted_assay_config(sample: dict):
    """Resolve and format the assay configuration for a sample document.

    Args:
        sample: Sample document containing assay and profile metadata.

    Returns:
        The formatted assay configuration payload, or ``None`` when no assay
        configuration is available for the sample.
    """
    assay_name = str(sample.get("assay") or "").strip()
    sample_name = str(sample.get("name") or sample.get("_id") or "unknown_sample").strip()
    environment = str(sample.get("profile", "production") or "production").strip() or "production"

    if not assay_name:
        raise validation_error(
            "Sample is missing assay metadata",
            f"Sample '{sample_name}' does not define an assay value.",
            hint="Populate the sample 'assay' field before opening analysis or report views.",
        )

    assay_panel = store.assay_panel_handler.get_asp(assay_name)
    if not assay_panel:
        raise setup_error(
            f"ASP not registered for assay '{assay_name}'",
            (
                f"Sample '{sample_name}' references assay '{assay_name}', "
                "but no ASP document is registered for that assay."
            ),
            hint="Create and activate the ASP for this assay before opening sample analysis pages.",
        )

    assay_config = store.assay_configuration_handler.get_aspc_no_meta(
        assay_name,
        environment,
    )
    if not assay_config:
        raise setup_error(
            f"ASPC not registered for assay '{assay_name}' in environment '{environment}'",
            (
                f"Sample '{sample_name}' belongs to environment '{environment}', "
                f"but no ASPC exists for assay '{assay_name}' in that environment."
            ),
            hint="Create and activate the ASPC for this assay/environment combination.",
        )
    omics = str(sample.get("omics_layer") or "").upper()
    if not omics:
        omics = "RNA" if sample.get("fusion_files") else "DNA"
    assay_config_schema = build_form_spec(aspc_spec_for_category(omics))
    return util.common.format_assay_config(deepcopy(assay_config), assay_config_schema)
