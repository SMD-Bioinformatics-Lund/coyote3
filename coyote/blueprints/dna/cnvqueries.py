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


def build_cnv_query(sample_id: str, filters: dict) -> dict:
    """
    A function build cnv queiry basedo on the sample filters and filter genes
    """
    query = {"SAMPLE_ID": sample_id}

    # TODO CHECK WHAT IS NORMAL IN THE PREVIOUS COYOTE
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
