"""Service-level DNA translocation query builders."""

from __future__ import annotations

import re
from typing import Any

from api.config.clinical_query_policy import (
    CLINICAL_QUERY_POLICY,
    FindingQueryException,
    FindingQueryPolicy,
)


def _gene_token_clause(gene: str) -> dict[str, Any]:
    token = re.escape(gene)
    predicate = {"$regex": rf"(?:^|&){token}(?:&|$)", "$options": "i"}
    return {
        "$or": [
            {"INFO.MANE_ANN.Gene_Name": predicate},
            {"INFO.ANN.Gene_Name": predicate},
        ]
    }


def _translocation_exception_clause(exception: FindingQueryException) -> dict[str, Any]:
    criteria = exception.criteria
    clauses: list[dict[str, Any]] = []
    if criteria.get("chromosomes"):
        clauses.append({"CHROM": {"$in": list(criteria["chromosomes"])}})
    if criteria.get("svtypes"):
        clauses.append({"INFO.SVTYPE": {"$in": list(criteria["svtypes"])}})
    if criteria.get("genes"):
        clauses.append({"$or": [_gene_token_clause(gene) for gene in criteria["genes"]]})
    if criteria.get("gene_pairs"):
        pairs: list[str] = []
        for value in criteria["gene_pairs"]:
            gene1, separator, gene2 = str(value).partition("--")
            if separator:
                pairs.extend((f"{gene1}&{gene2}", f"{gene2}&{gene1}"))
        clauses.append(
            {
                "$or": [
                    {"INFO.MANE_ANN.Gene_Name": {"$in": pairs}},
                    {"INFO.ANN.Gene_Name": {"$in": pairs}},
                ]
            }
        )
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def build_transloc_query(
    sample_id: str,
    settings: dict[str, Any] | None = None,
    *,
    policy: FindingQueryPolicy = CLINICAL_QUERY_POLICY.translocation,
) -> dict[str, Any]:
    """Build translocation query for a sample."""
    settings = settings or {}
    scope = {
        "assay_group": str(settings.get("assay_group") or "").strip().lower(),
        "asp_id": str(settings.get("asp_id") or "").strip().lower(),
        "subpanel_id": str(settings.get("subpanel_id") or "base").strip().lower(),
        "intent": str(settings.get("intent") or "somatic").strip().lower(),
    }
    exclusions = [
        _translocation_exception_clause(exception)
        for exception in policy.exceptions_for(**scope, mode="exclude")
    ]
    clauses: list[dict[str, Any]] = []
    if exclusions:
        clauses.append({"$nor": exclusions})
    return {"SAMPLE_ID": sample_id, **({"$and": clauses} if clauses else {})}


def translocation_genes(translocation: dict[str, Any]) -> list[str]:
    """Return normalized gene symbols carried by a translocation document."""
    gene_values: list[str] = []
    genes = translocation.get("genes")
    if isinstance(genes, list):
        for gene in genes:
            if isinstance(gene, dict):
                gene_values.append(str(gene.get("gene") or gene.get("symbol") or ""))
            elif gene:
                gene_values.append(str(gene))
    gene_values.extend(
        str(gene)
        for gene in (
            translocation.get("gene1") or translocation.get("GENE1"),
            translocation.get("gene2") or translocation.get("GENE2"),
        )
        if gene
    )

    info = translocation.get("INFO") or {}
    if isinstance(info, list):
        info = next((item for item in info if isinstance(item, dict)), {})
    if isinstance(info, dict):
        annotations: list[dict[str, Any]] = []
        mane = info.get("MANE_ANN")
        if isinstance(mane, dict):
            annotations.append(mane)
        annotations.extend(item for item in (info.get("ANN") or []) if isinstance(item, dict))
        for annotation in annotations:
            raw_names = annotation.get("Gene_Name") or annotation.get("SYMBOL") or ""
            gene_values.extend(str(raw_names).replace("::", "&").split("&"))

    return list(dict.fromkeys(value.strip().upper() for value in gene_values if str(value).strip()))


def filter_translocations_by_genes(
    translocations: list[dict[str, Any]],
    *,
    filter_genes: list[str],
    restricted: bool,
    settings: dict[str, Any] | None = None,
    policy: FindingQueryPolicy = CLINICAL_QUERY_POLICY.translocation,
) -> list[dict[str, Any]]:
    """Apply gene scope plus typed admissions and exclusions to translocations."""
    settings = settings or {}
    scope = {
        "assay_group": str(settings.get("assay_group") or "").strip().lower(),
        "asp_id": str(settings.get("asp_id") or "").strip().lower(),
        "subpanel_id": str(settings.get("subpanel_id") or "base").strip().lower(),
        "intent": str(settings.get("intent") or "somatic").strip().lower(),
    }
    admissions = policy.exceptions_for(**scope, mode="admit")
    exclusions = policy.exceptions_for(**scope, mode="exclude")
    allowed = {str(gene).strip().upper() for gene in filter_genes if str(gene).strip()}

    def matches_exception(translocation: dict[str, Any], exception: FindingQueryException) -> bool:
        criteria = exception.criteria
        genes = set(translocation_genes(translocation))
        if criteria.get("genes") and not genes.intersection(criteria["genes"]):
            return False
        if criteria.get("gene_pairs"):
            pairs = {
                "--".join(sorted(pair.split("--")))
                for pair in criteria["gene_pairs"]
                if "--" in pair
            }
            observed = "--".join(sorted(genes)) if len(genes) == 2 else ""
            if observed not in pairs:
                return False
        info = translocation.get("INFO") or {}
        if isinstance(info, list):
            info = next((item for item in info if isinstance(item, dict)), {})
        if criteria.get("svtypes") and str(info.get("SVTYPE") or "").upper() not in set(
            criteria["svtypes"]
        ):
            return False
        if criteria.get("chromosomes") and str(translocation.get("CHROM") or "").upper() not in set(
            criteria["chromosomes"]
        ):
            return False
        return True

    result: list[dict[str, Any]] = []
    for translocation in translocations:
        genes = set(translocation_genes(translocation))
        baseline_match = not restricted or bool(allowed & genes)
        admitted = any(matches_exception(translocation, rule) for rule in admissions)
        excluded = any(matches_exception(translocation, rule) for rule in exclusions)
        if (baseline_match or admitted) and not excluded:
            result.append(translocation)
    return result
