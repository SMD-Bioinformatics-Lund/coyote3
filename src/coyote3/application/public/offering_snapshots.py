"""Build reviewed catalog offerings from explicit, validated resource relationships."""

from copy import deepcopy
from typing import Any

from coyote3.contracts.schemas.catalog_offerings import CatalogOfferingDoc
from coyote3.domain.catalog_hierarchy import resolve_catalog_categories
from coyote3.domain.common.errors import api_error

LIST_KEYS = {
    "SNV": "snvlists",
    "CNV": "cnvlists",
    "FUSION": "fusionlists",
}


def configured_lists(value: Any, key: str) -> set[str]:
    """Collect explicit list selections for an analysis across configured intents.

    Args:
        value: Configuration filter subtree.
        key: Canonical analysis-specific list selector.

    Returns:
        Distinct selected list identifiers; missing selections contribute nothing.
    """
    if not isinstance(value, dict):
        return set()
    result = set(value.get(key) or []) if isinstance(value.get(key), list) else set()
    for child in value.values():
        if isinstance(child, dict):
            result.update(configured_lists(child, key))
    return result


def build_offering_snapshot(
    catalog: dict, *, panels, configurations, gene_lists, groups, diagnoses
) -> dict:
    """Capture public service content and private resource revision references.

    Args:
        catalog: Reviewed presentation entries with explicit configuration references.
        panels: Assay definition repository.
        configurations: Configuration repository.
        gene_lists: Public gene-list repository.
        groups: Biological group registry repository.
        diagnoses: Shared diagnosis and assay association repository.

    Returns:
        Catalog copy containing allowlisted offerings and separate resource provenance.

    Raises:
        AppError: A source is unavailable or presentation advertises unsupported scope.
    """
    result = deepcopy(catalog)
    offerings, revisions = [], {}
    modalities = catalog.get("modalities", {})
    order = dict.fromkeys([*(catalog.get("layout", {}).get("order") or []), *modalities])
    for key in order:
        modality = modalities.get(key)
        if modality is None:
            continue
        for entry in resolve_catalog_categories(modality).values():
            if entry.get("node_kind") == "folder":
                continue
            panel = panels.get_asp(entry["asp_id"])
            config_id = entry.get("aspc_id") or (entry.get("aspc_ids") or {}).get("production")
            config = configurations.get_aspc_with_id(config_id)
            if not panel or not config or not panel.get("is_active") or not config.get("is_active"):
                raise api_error(422, "Offering sources must be active")
            group_id = config["asp_group"]
            group = groups.get(group_id)
            diagnosis_id = entry.get("diagnosis_id") or "base"
            if (
                not group
                or not group.get("is_active")
                or panel["asp_group"] != group_id
                or config["asp_id"] != panel["asp_id"]
                or config["environment"] != "production"
                or (config.get("diagnosis_id") or "base") != diagnosis_id
                or not (config.get("catalog") or {}).get("is_public", True)
            ):
                raise api_error(422, "Offering must reference an eligible production context")
            diagnosis = None
            if diagnosis_id != "base":
                diagnosis = next(
                    (
                        item
                        for item in diagnoses.list_for_assay(panel["asp_id"], active_only=True)
                        if item["diagnosis_id"] == diagnosis_id
                    ),
                    None,
                )
                if diagnosis is None:
                    raise api_error(422, "Offering diagnosis must have an active assay association")
            analyses = list(entry.get("analysis") or [])
            supported = set(panel.get("supported_analyses") or [])
            if set(analyses) - (supported & set(config.get("analysis_types") or [])):
                raise api_error(
                    422, "Offering analyses must be enabled by the assay and configuration"
                )
            scopes, list_revisions = [], {}
            for binding in entry.get("gene_lists", []):
                list_id = binding.get("isgl_id") or binding.get("key")
                gene_list = gene_lists.get_isgl(list_id, is_active=True, is_public=True)
                if not gene_list:
                    raise api_error(422, "Offering gene lists must be active and public")
                genes = set(gene_list.get("genes") or [])
                coverage = set(panel.get("covered_genes") or [])
                for analysis in binding.get("analysis") or []:
                    selector = LIST_KEYS.get(analysis)
                    if (
                        analysis not in analyses
                        or not selector
                        or list_id not in configured_lists(config.get("filters"), selector)
                    ):
                        raise api_error(
                            422, "Public gene scope must be selected in its analysis configuration"
                        )
                    scopes.append(
                        {
                            "list_id": list_id,
                            "label": binding.get("label")
                            or gene_list.get("name")
                            or gene_list["displayname"],
                            "revision": gene_list["version"],
                            "analysis": analysis,
                            "genes": sorted(genes & coverage),
                            "excluded_gene_count": len(genes - coverage),
                        }
                    )
                list_revisions[list_id] = gene_list["version"]
            offering_id = entry["catalog_id"]
            offering = CatalogOfferingDoc(
                offering_id=offering_id,
                title=entry.get("title") or entry["label"],
                group_id=group_id,
                group_label=group["display_name"],
                diagnosis_id=diagnosis_id,
                diagnosis_label=diagnosis["display_name"]
                if diagnosis
                else "No diagnosis / General testing",
                modality=panel["asp_category"],
                family=panel["asp_family"],
                assay_id=panel["asp_id"],
                assay_label=panel["display_name"],
                description=entry.get("description") or "",
                analysis=analyses,
                price=entry.get("price"),
                pricing_message=entry.get("pricing_message") or "Contact for pricing",
                turnaround=entry.get("tat") or "",
                input_material=entry.get("input_material") or [],
                report_deliverables=entry.get("report_deliverables") or [],
                methodology=entry.get("methodology") or "",
                limitations=entry.get("limitations") or "",
                ordering_information=entry.get("ordering_information") or "",
                gene_scopes=scopes,
            )
            offerings.append(offering.model_dump(mode="json"))
            revisions[offering_id] = {
                "assay_id": panel["asp_id"],
                "assay_revision": panel["version"],
                "configuration_id": config_id,
                "configuration_revision": config["version"],
                "group_revision": group["version"],
                "gene_lists": list_revisions,
                "diagnosis_revision": diagnosis.get("version") if diagnosis else None,
                "diagnosis_definition_revision": diagnosis.get("definition_version")
                if diagnosis
                else None,
            }
    result["published_offerings"] = offerings
    result["resource_revisions"] = revisions
    return result
