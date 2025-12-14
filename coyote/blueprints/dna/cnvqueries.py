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

"""
This module provides functions for constructing MongoDB queries to retrieve Copy Number Variation (CNV) records
based on sample identifiers and customizable filter criteria. It is part of the Coyote3 framework for genomic data
analysis, interpretation, and clinical diagnostics.
"""


def build_cnv_query(sample_id: str, filters: dict) -> dict:
    """
    Build a CNV (Copy Number Variation) query based on the provided sample ID and filter criteria.

    Args:
        sample_id (str): The unique identifier for the sample.
        filters (dict): A dictionary containing filter parameters, which may include:
            - cnv_loss_cutoff (float): Lower threshold for CNV loss.
            - cnv_gain_cutoff (float): Upper threshold for CNV gain.
            - min_cnv_size (int): Minimum CNV size to include.
            - max_cnv_size (int): Maximum CNV size to include.
            - filter_genes (list): List of gene names to filter by.

    Returns:
        dict: A MongoDB query dictionary for retrieving CNV records matching the criteria.
    """
    query = {"SAMPLE_ID": sample_id}

    if filters:
        query = {
            "SAMPLE_ID": sample_id,
            "$and": [
                # Filter by NORMAL status:
                {
                    "$or": [
                        {"NORMAL": {"$ne": 1}},
                        {"NORMAL": {"$exists": False}},
                    ]
                },
                # Ratio Condition: (cnv.ratio|float < -0.3 or cnv.ratio|float > 0.3)
                {
                    "$or": [
                        {"ratio": {"$lte": filters["cnv_loss_cutoff"]}},
                        {"ratio": {"$gte": filters["cnv_gain_cutoff"]}},
                    ]
                },
                # Size and Ratio Condition:
                {
                    "$or": [
                        {
                            "$and": [
                                {"size": {"$gte": filters["min_cnv_size"]}},
                                {"size": {"$lte": filters["max_cnv_size"]}},
                            ]
                        },
                    ]
                },
                # Gene Panel Condition:
                {
                    "$or": [
                        {
                            "panel_gene": {
                                "$in": filters.get("filter_genes", [])
                            }
                        },
                        {
                            "panel_gene": {"$exists": False}
                        },  # Handle empty dispgenes with $exists
                        {"assay": "tumwgs"},
                    ]
                },
            ],
        }

    return query
