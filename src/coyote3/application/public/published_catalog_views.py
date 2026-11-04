"""Read-only catalog views derived exclusively from approved offering snapshots."""

from collections import Counter

from coyote3.contracts.schemas.catalog_offerings import (
    CatalogDiscoveryDoc,
    CatalogNavigationNodeDoc,
)
from coyote3.domain.catalog_hierarchy import resolve_catalog_categories
from coyote3.domain.common.errors import api_error


def catalog_discovery(document: dict) -> dict:
    """Expose reviewed hierarchy wording and frozen offerings through an explicit allowlist.

    Args:
        document: Stored publication or validated private preview snapshot.

    Returns:
        Discovery payload with resolved parent presentation, excluding configuration
        identifiers, resource revisions and arbitrary authoring metadata.
    """
    nodes = []
    discovery = CatalogDiscoveryDoc(
        version=document.get("version", 0),
        header=document.get("header") or "Genomic test catalog",
        description=document.get("description") or "",
        offerings=document.get("published_offerings") or [],
    )
    offerings = discovery.model_dump(mode="json")["offerings"]
    offering_ids = {item["offering_id"] for item in offerings}
    modalities = document.get("modalities") or {}
    order = dict.fromkeys([*(document.get("layout", {}).get("order") or []), *modalities])
    for section_key in order:
        section = modalities.get(section_key)
        if section is None:
            continue
        section_id = f"section:{section_key}"
        entries = [(section_id, None, section_key, section)]
        for key, entry in resolve_catalog_categories(section).items():
            parent = entry.get("parent_key")
            entries.append(
                (
                    f"entry:{section_key}:{key}",
                    f"entry:{section_key}:{parent}" if parent else section_id,
                    key,
                    entry,
                )
            )
        for node_id, parent_id, key, entry in entries:
            public = {
                field: entry.get(field) or default
                for field, default in (
                    ("description", ""),
                    ("subheading", ""),
                    ("input_material", []),
                    ("sample_modes", []),
                    ("analysis", []),
                    ("clinical_indications", []),
                    ("limitations", ""),
                    ("public_notes", ""),
                    ("methodology", ""),
                    ("ordering_information", ""),
                )
            }
            offering_id = entry.get("catalog_id")
            nodes.append(
                CatalogNavigationNodeDoc(
                    node_id=node_id,
                    parent_id=parent_id,
                    offering_id=offering_id if offering_id in offering_ids else None,
                    label=entry.get("label") or entry.get("title") or key,
                    title=entry.get("title") or entry.get("label") or key,
                    turnaround=entry.get("tat") or "",
                    report_deliverables=entry.get("report_deliverables")
                    or entry.get("report_sections")
                    or [],
                    **public,
                    price=entry.get("price"),
                    pricing_message=entry.get("pricing_message") or "",
                    clear_fields=entry.get("clear_fields") or [],
                )
            )
    discovery.navigation = nodes
    return discovery.model_dump(mode="json")


def publication_context(
    publication: dict,
    mod: str | None = None,
    cat: str | None = None,
    isgl_key: str | None = None,
) -> dict:
    """Project a publication into navigation and effective gene rows.

    Args:
        publication: Allowlisted discovery document.
        mod: Optional molecular modality.
        cat: Optional offering identifier within the modality.
        isgl_key: Optional published list identifier.

    Returns:
        Navigation, selected offering, and frozen gene scope.

    Raises:
        AppError: A requested offering or list is not in the publication.
    """
    modalities = {}
    for item in publication["offerings"]:
        section = modalities.setdefault(
            item["modality"],
            {
                "label": item["modality"].upper(),
                "categories": {},
            },
        )
        section["categories"][item["offering_id"]] = {
            "label": item["title"],
            "analysis": item["analysis"],
        }
    selected = [
        item
        for item in publication["offerings"]
        if (not mod or item["modality"] == mod) and (not cat or item["offering_id"] == cat)
    ]
    if (mod or cat or isgl_key) and not selected:
        raise api_error(404, "Published offering not found")
    scopes = [
        scope
        for item in selected
        for scope in item["gene_scopes"]
        if not isgl_key or scope["list_id"] == isgl_key
    ]
    if isgl_key and not scopes:
        raise api_error(404, "Published gene scope not found")
    genes = sorted({gene for scope in scopes for gene in scope["genes"]}) if mod or cat else []
    return {
        "meta": {"version": publication["version"]},
        "order": list(modalities),
        "modalities": modalities,
        "selected_mod": mod,
        "selected_cat": cat,
        "selected_isgl": isgl_key,
        "categories": list(modalities.get(mod, {}).get("categories", {}).values()),
        "right": selected[0]
        if cat
        else {"title": publication["header"], "description": publication["description"]},
        "gene_mode": "published",
        "genes": [{"symbol": gene, "display_symbol": gene} for gene in genes],
        "stats": {"total": len(genes), "covered_total": len(genes), "germline_total": 0},
    }


def publication_matrix(
    publication: dict, *, page: int = 1, per_page: int = 100, gene: str | None = None
) -> dict:
    """Compare only effective analysis scopes contained in the publication.

    Args:
        publication: Allowlisted discovery document.
        page: One-based result page.
        per_page: Maximum number of gene rows per page.
        gene: Optional case-insensitive gene substring.

    Returns:
        Paginated matrix with separate list and analysis columns.
    """
    columns, scopes = [], []
    for item in publication["offerings"]:
        for scope in item["gene_scopes"]:
            columns.append(
                {
                    "mod": item["modality"],
                    "cat": item["offering_id"],
                    "family": item["family"],
                    "assay_group": item["group_label"],
                    "assay_id": item["assay_id"],
                    "assay": item["assay_label"],
                    "diagnosis_id": item["diagnosis_id"],
                    "diagnosis": item["diagnosis_label"],
                    "cat_label": item["title"],
                    "isgl_key": f"{scope['list_id']}:{scope['analysis']}",
                    "isgl_label": scope["label"],
                    "analysis": scope["analysis"],
                    "placeholder": False,
                    "modality_label": item["modality"].upper(),
                }
            )
            scopes.append(set(scope["genes"]))
    genes = sorted(
        {
            symbol
            for scope in scopes
            for symbol in scope
            if not gene or gene.upper() in symbol.upper()
        }
    )
    visible = genes[(page - 1) * per_page : page * per_page]
    matrix = {}
    for symbol in visible:
        matrix[symbol] = {}
        for column, scope in zip(columns, scopes, strict=True):
            matrix[symbol].setdefault(column["mod"], {}).setdefault(column["cat"], {})[
                column["isgl_key"]
            ] = symbol in scope
    modalities = publication_context(publication)["modalities"]
    return {
        "modalities": modalities,
        "order": list(modalities),
        "columns": columns,
        "mod_spans": dict(Counter(column["mod"] for column in columns)),
        "cat_spans": dict(Counter(f"{column['mod']}::{column['cat']}" for column in columns)),
        "genes": visible,
        "matrix": matrix,
        "gene_markers": {},
        "page": page,
        "per_page": per_page,
        "total": len(genes),
        "search": gene,
        "has_next": page * per_page < len(genes),
        "has_previous": page > 1,
    }
