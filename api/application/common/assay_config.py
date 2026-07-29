"""Assay configuration resolution for application services."""

from __future__ import annotations

from copy import deepcopy

from api.config.constants import (
    DEFAULT_ENVIRONMENT,
    SUBPANEL_BASE_ID,
    normalize_clinical_identifier,
    primary_analysis_file_key,
)
from api.contracts.managed_resources import aspc_spec_for_category
from api.contracts.managed_ui_schemas import build_form_spec
from api.domain.common.assay_filters import format_assay_config
from api.domain.common.errors import setup_error, validation_error


def get_formatted_assay_config(
    sample: dict,
    *,
    assay_panel_repository,
    assay_configuration_repository,
) -> dict:
    """Resolve and format the assay configuration for a sample document."""
    sample_name = str(sample.get("name") or sample.get("_id") or "unknown_sample").strip()
    raw_asp_id = sample.get("asp_id")
    if not str(raw_asp_id or "").strip():
        raise validation_error(
            "Sample is missing assay metadata",
            f"Sample '{sample_name}' does not define an ASP identifier.",
            hint="Populate sample.asp_id before opening analysis or report views.",
        )
    assay_name = normalize_clinical_identifier(raw_asp_id, label="asp_id")
    environment = (
        str(sample.get("environment", DEFAULT_ENVIRONMENT) or DEFAULT_ENVIRONMENT).strip()
        or DEFAULT_ENVIRONMENT
    )
    requested_subpanel_id = normalize_clinical_identifier(
        sample.get("subpanel_id") or SUBPANEL_BASE_ID,
        label="subpanel_id",
    )

    assay_panel = assay_panel_repository.get_asp(assay_name)
    if not assay_panel:
        raise setup_error(
            f"ASP not registered for assay '{assay_name}'",
            (
                f"Sample '{sample_name}' references assay '{assay_name}', "
                "but no ASP document is registered for that assay."
            ),
            hint="Create and activate the ASP for this assay before opening sample analysis pages.",
        )

    assay_config = assay_configuration_repository.get_aspc_no_meta(
        assay_name,
        environment,
        requested_subpanel_id,
    )
    used_base_configuration = False
    if not assay_config and requested_subpanel_id != SUBPANEL_BASE_ID:
        assay_config = assay_configuration_repository.get_aspc_no_meta(
            assay_name,
            environment,
            SUBPANEL_BASE_ID,
        )
        used_base_configuration = bool(assay_config)
    if not assay_config:
        raise setup_error(
            (
                f"ASPC not registered for assay '{assay_name}', "
                f"subpanel '{requested_subpanel_id}', environment '{environment}'"
            ),
            (
                f"Sample '{sample_name}' belongs to environment '{environment}', "
                f"but no active ASPC exists for assay '{assay_name}' and subpanel "
                f"'{requested_subpanel_id}', and no active base ASPC is available."
            ),
            hint="Create and activate the ASPC for this assay/subpanel/environment combination or its base configuration.",
        )
    omics = str(sample.get("omics_layer") or "").upper()
    if not omics:
        omics = "RNA" if sample.get(primary_analysis_file_key("rna", "FUSION")) else "DNA"
    assay_config_schema = build_form_spec(aspc_spec_for_category(omics))
    formatted = format_assay_config(deepcopy(assay_config), assay_config_schema)
    formatted["aspc_resolution"] = {
        "requested_subpanel_id": requested_subpanel_id,
        "resolved_subpanel_id": formatted.get("subpanel_id") or SUBPANEL_BASE_ID,
        "used_base_configuration": used_base_configuration,
        "warning": (
            "No subpanel-specific ASPC is active; base configuration is in use."
            if used_base_configuration
            else None
        ),
    }
    return formatted
