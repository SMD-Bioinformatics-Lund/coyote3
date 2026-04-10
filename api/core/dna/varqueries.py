"""Service-level DNA SNV query builders."""

from __future__ import annotations

import re
from typing import Any


def _case_clause(settings: dict[str, Any]) -> dict[str, Any]:
    return {
        "GT": {
            "$elemMatch": {
                "type": "case",
                "AF": {
                    "$gte": float(settings["min_freq"]),
                    "$lte": float(settings["max_freq"]),
                },
                "DP": {"$gte": float(settings["min_depth"])},
                "VD": {"$gte": float(settings["min_alt_reads"])},
            }
        }
    }


def _control_clause(settings: dict[str, Any]) -> dict[str, Any]:
    return {
        "$or": [
            {
                "GT": {
                    "$elemMatch": {
                        "type": "control",
                        "AF": {"$lte": float(settings["max_control_freq"])},
                        "DP": {"$gte": float(settings["min_depth"])},
                    }
                }
            },
            {"GT": {"$not": {"$elemMatch": {"type": "control"}}}},
        ]
    }


def _popfreq_clause(settings: dict[str, Any]) -> dict[str, Any]:
    return {
        "$or": [
            {
                "gnomad_frequency": {
                    "$exists": True,
                    "$type": "number",
                    "$lte": float(settings["max_popfreq"]),
                }
            },
            {"gnomad_frequency": {"$type": "string"}},
            {"gnomad_frequency": None},
            {"gnomad_frequency": {"$exists": False}},
        ]
    }


def _consequence_clause(settings: dict[str, Any]) -> dict[str, Any]:
    return {
        "$or": [
            {"INFO.selected_CSQ.Consequence": {"$in": settings["filter_conseq"]}},
            {
                "INFO.CSQ": {
                    "$elemMatch": {
                        "Consequence": {"$in": settings["filter_conseq"]},
                    }
                }
            },
        ]
    }


def _flt3_large_indel_escape(large_ins_regex: re.Pattern[str]) -> dict[str, Any]:
    return {
        "$and": [
            {"genes": {"$in": ["FLT3"]}},
            {
                "$or": [
                    {"INFO.SVTYPE": {"$exists": True}},
                    {"ALT": large_ins_regex},
                ]
            },
        ]
    }


def _generic_germline_clause(settings: dict[str, Any]) -> dict[str, Any]:
    _ = settings
    return {
        "$or": [
            {"INFO.MYELOID_GERMLINE": 1},
            {
                "FILTER": {"$in": ["GERMLINE"]},
                "INFO.CSQ": {"$elemMatch": {"SYMBOL": "CEBPA"}},
            },
            {
                "$and": [
                    {"POS": {"$gt": 115256520}},
                    {"POS": {"$lt": 115256538}},
                    {"CHROM": 1},
                ]
            },
        ]
    }


def _generic_somatic_clause(
    settings: dict[str, Any], large_ins_regex: re.Pattern[str]
) -> dict[str, Any]:
    return {
        "$and": [
            _case_clause(settings),
            _control_clause(settings),
            _popfreq_clause(settings),
            {
                "$or": [
                    _consequence_clause(settings),
                    _flt3_large_indel_escape(large_ins_regex),
                ]
            },
        ]
    }


def build_query(assay_group: str, settings: dict) -> dict:
    """Construct an SNV query from assay-group defaults and ASPC overlay."""
    large_ins_regex = re.compile(r"\w{10,200}", re.IGNORECASE)
    gene_pos_filter = build_pos_genes_filter(settings)
    normalized_group = str(assay_group or "").strip().lower()

    query: dict[str, Any] = {"SAMPLE_ID": settings["id"]}

    if normalized_group in {"generic_germline"}:
        query = {
            "SAMPLE_ID": settings["id"],
            "$and": [
                gene_pos_filter,
                _generic_germline_clause(settings),
            ],
        }

    elif normalized_group in {"generic_somatic"}:
        query = {
            "SAMPLE_ID": settings["id"],
            "$and": [
                gene_pos_filter,
                _generic_somatic_clause(settings, large_ins_regex),
            ],
        }

    elif normalized_group in {"myeloid", "hematology", "tumwgs", "unknown"}:
        query = {
            "SAMPLE_ID": settings["id"],
            "$and": [
                gene_pos_filter,
                {
                    "$or": [
                        _generic_germline_clause(settings),
                        _generic_somatic_clause(settings, large_ins_regex),
                    ],
                },
            ],
        }

    elif normalized_group == "solid":
        query = {
            "SAMPLE_ID": settings["id"],
            "$and": [
                gene_pos_filter,
                {
                    "$or": [
                        {"FILTER": {"$in": ["GERMLINE"]}},
                        {
                            "$and": [
                                _case_clause(settings),
                                _control_clause(settings),
                                _popfreq_clause(settings),
                                {
                                    "$or": [
                                        _consequence_clause(settings),
                                        {
                                            "$and": [
                                                {"$or": [{"genes": {"$in": ["TERT", "NFKBIE"]}}]},
                                                {
                                                    "$or": [
                                                        {
                                                            "INFO.selected_CSQ.Consequence": {
                                                                "$in": [
                                                                    "regulatory_region_variant",
                                                                    "TF_binding_site_variant",
                                                                ]
                                                            }
                                                        },
                                                        {
                                                            "INFO.CSQ": {
                                                                "$elemMatch": {
                                                                    "Consequence": {
                                                                        "$in": [
                                                                            "regulatory_region_variant",
                                                                            "TF_binding_site_variant",
                                                                        ]
                                                                    }
                                                                }
                                                            }
                                                        },
                                                    ]
                                                },
                                            ]
                                        },
                                    ]
                                },
                            ]
                        },
                    ],
                },
            ],
        }

    return query


def build_pos_genes_filter(settings: dict) -> dict:
    """Build optional POS/gene/fp/irrelevant partial filters."""
    pos_list = settings.get("disp_pos", [])
    genes_list = settings.get("filter_genes", [])
    fp = settings.get("fp", "")
    irrelevant = settings.get("irrelevant", "")

    partial_query = {}

    if pos_list:
        partial_query["POS"] = {"$in": pos_list}
    elif genes_list:
        partial_query["genes"] = {"$in": genes_list}

    if fp:
        partial_query["fp"] = fp

    if irrelevant:
        partial_query["irrelevant"] = irrelevant

    if partial_query:
        return {"$and": [partial_query]}
    return {}
