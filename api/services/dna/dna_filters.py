#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#

"""Shared DNA filter helpers used by workflow/view layers."""

from typing import Any

from api.runtime import app


def _resolve_conseq_terms_mapper(conseq_terms_mapper: dict[str, Any] | None = None) -> dict[str, Any]:
    if conseq_terms_mapper is not None:
        return conseq_terms_mapper

    try:
        conf = app.config.get("CONSEQ_TERMS_MAPPER")
        if isinstance(conf, dict):
            return conf
    except RuntimeError:
        pass

    try:
        from api.extensions import store

        app_obj = getattr(getattr(store, "adapter", None), "app", None)
        if app_obj:
            conf = app_obj.config.get("CONSEQ_TERMS_MAPPER")
            if isinstance(conf, dict):
                return conf
    except Exception:
        pass
    return {}


def get_filter_conseq_terms(checked: list, conseq_terms_mapper: dict[str, Any] | None = None) -> list:
    """
    Return mapped consequence terms from checked form fields.
    """
    filter_conseq = []
    conf = _resolve_conseq_terms_mapper(conseq_terms_mapper)
    try:
        for fieldname in checked:
            if fieldname in conf:
                filter_conseq.extend(conf.get(fieldname))
    except (KeyError, TypeError):
        pass
    return filter_conseq


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
