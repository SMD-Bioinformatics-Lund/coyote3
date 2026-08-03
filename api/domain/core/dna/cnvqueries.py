"""Service-level DNA CNV query builders."""

from __future__ import annotations


def include_normal_cnvs(sample: dict, assay_panel: dict | None = None) -> bool:
    """Return whether the sample scope includes normal/control CNV records.

    Targeted panels review tumour calls separately from records marked as
    normal. Whole-genome analysis retains both in the same review table, as in
    the established TumWGS workflow.
    """
    panel = assay_panel or {}
    sequencing_scope = (
        str(sample.get("sequencing_scope") or sample.get("asp_family") or "").strip().lower()
    )
    panel_family = (
        str(panel.get("asp_family") or panel.get("sequencing_scope") or "").strip().lower()
    )
    assay_group = (
        str(
            sample.get("asp_group")
            or sample.get("assay_group")
            or panel.get("asp_group")
            or panel.get("assay_group")
            or ""
        )
        .strip()
        .lower()
    )
    return sequencing_scope == "wgs" or panel_family == "wgs" or assay_group == "tumwgs"


def build_cnv_query(sample_id: str, filters: dict, *, include_normal: bool = False) -> dict:
    """Build a CNV query for a sample based on configured filter criteria."""
    clauses: list[dict] = []

    if not include_normal:
        clauses.append(
            {
                "$or": [
                    {"NORMAL": {"$ne": 1}},
                    {"NORMAL": {"$exists": False}},
                ]
            }
        )

    if filters:
        ratio_outside_thresholds = {
            "$or": [
                {"ratio": {"$lt": filters["cnv_loss_cutoff"]}},
                {"ratio": {"$gt": filters["cnv_gain_cutoff"]}},
            ]
        }
        size_within_thresholds = {
            "$and": [
                {"size": {"$gt": filters["min_cnv_size"]}},
                {"size": {"$lt": filters["max_cnv_size"]}},
            ]
        }
        high_level_amplification = {"ratio": {"$gt": 3}}
        missing_ratio = {
            "$or": [
                {"ratio": None},
                {"ratio": {"$exists": False}},
            ]
        }
        structural_read_evidence = {
            "$or": [
                {"SR": {"$exists": True, "$nin": [None, "", []]}},
                {"PR": {"$exists": True, "$nin": [None, "", []]}},
            ]
        }

        # Ratio callers use copy-number and size thresholds. Structural callers
        # such as Manta have no ratio and are admitted by split/paired-read
        # evidence instead; applying ratio or minimum-size filters to those
        # records would silently remove valid breakpoints.
        clauses.append(
            {
                "$or": [
                    {
                        "$and": [
                            ratio_outside_thresholds,
                            {
                                "$or": [
                                    size_within_thresholds,
                                    high_level_amplification,
                                ]
                            },
                        ]
                    },
                    {
                        "$and": [
                            missing_ratio,
                            structural_read_evidence,
                        ]
                    },
                ]
            }
        )
        if filters.get("restrict_to_genes") and not filters.get("filter_genes"):
            clauses.append({"_id": {"$exists": False}})
        elif filters.get("filter_genes"):
            clauses.append(
                {
                    "$or": [
                        {"genes.gene": {"$in": filters.get("filter_genes", [])}},
                        {"panel_gene": {"$in": filters.get("filter_genes", [])}},
                    ]
                }
            )

    if not clauses:
        return {"SAMPLE_ID": sample_id}
    return {"SAMPLE_ID": sample_id, "$and": clauses}
