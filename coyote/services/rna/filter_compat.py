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
Backward-compatible RNA filter compatibility wrapper.
"""

from coyote.services.workflow.filter_normalization import (
    normalize_rna_filter_keys as shared_normalize_rna_filter_keys,
)


def normalize_rna_filter_keys(filters: dict | None) -> dict:
    """
    Return a compatibility-normalized RNA filter dict.

    Behavior:
    - Keep all existing keys untouched.
    - Ensure canonical keys exist for downstream query/form logic:
      - `min_spanning_reads`
      - `min_spanning_pairs`
    - If canonical key is missing, backfill from legacy key.
    - Values are coerced to non-negative ints for stability.
    """
    return shared_normalize_rna_filter_keys(filters)
