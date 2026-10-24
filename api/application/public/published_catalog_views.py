"""Read-only catalog views derived exclusively from approved offering snapshots."""

from collections import Counter

from api.domain.common.errors import api_error


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
                    "assay": item["assay_label"],
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
