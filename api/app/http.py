"""Common HTTP-layer helpers for the API."""

from __future__ import annotations

from copy import deepcopy

from api.app.container import store
from api.contracts.managed_resources import aspc_spec_for_category
from api.contracts.managed_ui_schemas import build_form_spec
from api.domain.common.assay_filters import format_assay_config
from api.domain.common.errors import (
    api_error,
    setup_error,
    validation_error,
)


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

    assay_panel = store.assay_panel_repository.get_asp(assay_name)
    if not assay_panel:
        raise setup_error(
            f"ASP not registered for assay '{assay_name}'",
            (
                f"Sample '{sample_name}' references assay '{assay_name}', "
                "but no ASP document is registered for that assay."
            ),
            hint="Create and activate the ASP for this assay before opening sample analysis pages.",
        )

    assay_config = store.assay_configuration_repository.get_aspc_no_meta(
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
    return format_assay_config(deepcopy(assay_config), assay_config_schema)


__all__ = ["api_error", "get_formatted_assay_config"]
