"""Compile operational configurations from validated installation resource bundles."""

from coyote3.application.common.release_resources import capture_assay_resource, capture_gene_lists


def compile_bundle_configurations(documents: dict[str, list[dict]]) -> None:
    """Compile staged configuration artifacts before installation writes any records.

    Args:
        documents: Validated resource bundle; configuration artifacts are populated in place.

    Raises:
        KeyError: A configuration references an assay absent from the bundle.
        ValueError: A named diagnosis lacks its definition or explicit assay association.
    """
    panels = {panel["asp_id"]: panel for panel in documents.get("assay_specific_panels", [])}
    definitions = {
        row["diagnosis_id"] for row in documents.get("diagnoses", []) if row.get("is_active", True)
    }
    associations = {
        (row["asp_id"], row["diagnosis_id"])
        for row in documents.get("diagnosis_associations", [])
        if row.get("is_active", True)
    }
    for configuration in documents.get("asp_configs", []):
        panel = panels[configuration["asp_id"]]
        diagnosis = configuration["diagnosis_id"]
        if diagnosis != "base" and (
            diagnosis not in definitions or (panel["asp_id"], diagnosis) not in associations
        ):
            raise ValueError(
                "Configuration requires an explicit shared diagnosis and assay association"
            )
        configuration["assay_resource_release"] = capture_assay_resource(panel)
        configuration["gene_list_release"] = capture_gene_lists(
            [
                item
                for item in documents.get("insilico_genelists", [])
                if item.get("is_active")
                and not item.get("adhoc")
                and (
                    configuration["asp_id"] in (item.get("asp_ids") or [])
                    or configuration["asp_group"] in (item.get("asp_groups") or [])
                )
            ]
        )
        for key in ("query_policy_release", "clinical_rule_release", "clinical_rule_base"):
            configuration.pop(key, None)
