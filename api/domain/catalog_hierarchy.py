"""Resolve catalog presentation inheritance without changing clinical configuration."""

from copy import deepcopy
from typing import Any

INHERITED_CATALOG_FIELDS = (
    "description",
    "subheading",
    "input_material",
    "sample_modes",
    "analysis",
    "report_sections",
    "clinical_indications",
    "tat",
    "limitations",
    "public_notes",
    "asp_id",
    "aspc_id",
    "aspc_ids",
    "subpanel_id",
    "gene_lists",
    "no_gene_list",
)


def resolve_catalog_categories(modality: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Resolve each entry against its immediate parent, retaining local identities.

    Args:
        modality: Section with categories linked by optional parent_key values.

    Returns:
        Independent resolved entries. Blank fields inherit; nonempty fields replace.
        Fields named in clear_fields explicitly suppress inheritance.

    Raises:
        ValueError: A parent is missing or the hierarchy contains a cycle.
    """
    categories = modality.get("categories") or {}
    resolved: dict[str, dict[str, Any]] = {}
    for key in categories:
        path: list[str] = []
        current = key
        while current and current not in resolved:
            if current in path:
                raise ValueError("Catalog hierarchy cannot contain a cycle")
            if current not in categories:
                raise ValueError("Catalog parent must be an entry in the same section")
            path.append(current)
            current = categories[current].get("parent_key")
        for item_key in reversed(path):
            item = deepcopy(categories[item_key])
            parent = resolved.get(item.get("parent_key"), modality)
            for field in INHERITED_CATALOG_FIELDS:
                if field in (item.get("clear_fields") or []):
                    continue
                if item.get(field) in (None, "", [], {}):
                    if field in parent:
                        item[field] = deepcopy(parent[field])
            # Analyses marked as having no list must not retain inherited list bindings.
            excluded = set(item.get("no_gene_list") or [])
            if excluded and not categories[item_key].get("gene_lists"):
                item["gene_lists"] = [
                    {**gene, "analysis": [a for a in gene.get("analysis", []) if a not in excluded]}
                    for gene in item.get("gene_lists") or []
                    if set(gene.get("analysis") or []) - excluded
                ]
            resolved[item_key] = item
    return {key: resolved[key] for key in categories}
