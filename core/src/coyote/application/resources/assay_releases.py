# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Bind an operational configuration to the exact assay and selectable gene-list revisions."""

from typing import Any

from coyote.application.common.release_resources import capture_assay_resource, capture_gene_lists
from coyote.application.resources.aspc import AspcService
from coyote.domain.common.errors import api_error


def bind_resources(
    configuration: dict[str, Any], panel: dict[str, Any], lists: list[dict[str, Any]]
) -> dict[str, Any]:
    """Capture current resources and reject changes that invalidate existing analysis settings."""
    if configuration["asp_category"] != panel["asp_category"]:
        raise api_error(409, f"{configuration['aspc_id']} requires its original assay category")
    AspcService.validate_analysis_types_for_panel(configuration, panel)
    selectable = {row["isgl_id"]: row for row in lists}
    for intent in (configuration.get("filters") or {}).values():
        for section in (intent or {}).values():
            for field, kind in (
                ("snvlists", "snv"),
                ("cnvlists", "cnv"),
                ("fusionlists", "fusion"),
            ):
                for identifier in (section or {}).get(field) or []:
                    if kind not in selectable.get(identifier, {}).get("list_type", []):
                        raise api_error(
                            409,
                            f"{configuration['aspc_id']} uses gene list {identifier} for {kind}. Change its filter selection before withdrawing the list.",
                        )
    return {
        **configuration,
        "asp_group": panel["asp_group"],
        "platform": panel.get("platform"),
        "assay_resource_release": capture_assay_resource(panel),
        "gene_list_release": capture_gene_lists(lists),
    }
