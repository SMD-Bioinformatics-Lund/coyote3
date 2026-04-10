"""Service-level DNA CNV query builders."""

from __future__ import annotations


def build_cnv_query(sample_id: str, filters: dict) -> dict:
    """Build a CNV query for a sample based on configured filter criteria."""
    query = {"SAMPLE_ID": sample_id}

    if filters:
        clauses: list[dict] = []
        clauses.append(
            {
                "$or": [
                    {"NORMAL": {"$ne": 1}},
                    {"NORMAL": {"$exists": False}},
                ]
            }
        )
        clauses.append(
            {
                "$or": [
                    {"ratio": {"$lte": filters["cnv_loss_cutoff"]}},
                    {"ratio": {"$gte": filters["cnv_gain_cutoff"]}},
                ]
            }
        )
        clauses.append(
            {
                "$or": [
                    {
                        "$and": [
                            {"size": {"$gte": filters["min_cnv_size"]}},
                            {"size": {"$lte": filters["max_cnv_size"]}},
                        ]
                    },
                ]
            }
        )
        if filters.get("filter_genes"):
            clauses.append(
                {
                    "$or": [
                        {"genes.gene": {"$in": filters.get("filter_genes", [])}},
                        {"panel_gene": {"$in": filters.get("filter_genes", [])}},
                        {"panel_gene": {"$exists": False}},
                        {"assay": "tumwgs"},
                    ]
                }
            )

        if clauses:
            query = {
                "SAMPLE_ID": sample_id,
                "$and": clauses,
            }

    return query
