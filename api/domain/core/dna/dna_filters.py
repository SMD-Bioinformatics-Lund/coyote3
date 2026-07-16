"""Common DNA filter helpers used by workflow/view layers."""

from typing import Any


def get_filter_conseq_terms(checked: list, conseq_terms_mapper: dict[str, Any]) -> list:
    """Return mapped consequence terms from checked form fields.

    Args:
        checked: Selected filter keys from the request/UI layer.
        conseq_terms_mapper: Mapping from UI keys to normalized consequence terms.

    Returns:
        list: Flattened consequence terms for query construction.
    """
    mapper = conseq_terms_mapper or {}
    filter_conseq = []
    try:
        for fieldname in checked:
            normalized = str(fieldname or "").strip()
            if normalized in mapper:
                filter_conseq.extend(mapper.get(normalized) or [])
            elif normalized.endswith("_variant") or normalized in {
                "stop_gained",
                "stop_lost",
                "start_lost",
            }:
                filter_conseq.append(normalized)
    except (KeyError, TypeError):
        pass
    return list(dict.fromkeys(filter_conseq))


def create_cnveffectlist(cnvtype: list) -> list:
    """
    Translate CNV effect filters from UI values to annotation codes.
    """
    types = []
    for name in cnvtype:
        if name == "loss":
            types.append("DEL")
        if name == "gain":
            types.append("AMP")
    return types


def cnvtype_variant(cnvs: list, checked_effects: list) -> list:
    """
    Filter CNV rows by inferred effect (AMP/DEL).
    """
    filtered_cnvs = []
    for var in cnvs:
        effect = None
        if var["ratio"] > 0:
            effect = "AMP"
        elif var["ratio"] < 0:
            effect = "DEL"
        if effect and effect in checked_effects:
            filtered_cnvs.append(var)
    return filtered_cnvs


def cnv_organizegenes(cnvs: list) -> list:
    """
    Split CNV genes into panel genes and other genes.
    """
    fixed_cnvs_genes = []
    for var in cnvs:
        var["other_genes"] = []
        for gene in var["genes"]:
            if "class" in gene:
                if "panel_gene" in var:
                    var["panel_gene"].append(gene["gene"])
                else:
                    var["panel_gene"] = [gene["gene"]]
            else:
                var["other_genes"].append(gene["gene"])
        fixed_cnvs_genes.append(var)
    return fixed_cnvs_genes
