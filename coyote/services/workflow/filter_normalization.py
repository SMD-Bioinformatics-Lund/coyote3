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
Shared filter coercion/normalization helpers for workflow services.
"""

from typing import Any


def coerce_nonnegative_int(value: Any, default: int = 0) -> int:
    """
    Coerce incoming filter values to non-negative integers.
    Handles mixed string/int form and persisted values.
    """
    try:
        parsed = int(value)
        return parsed if parsed >= 0 else default
    except (TypeError, ValueError):
        return default


def normalize_rna_filter_keys(filters: dict | None) -> dict:
    """
    Return RNA filter dict with canonical spanning-read/pair keys ensured.
    """
    normalized = dict(filters or {})
    min_reads = normalized.get("min_spanning_reads", normalized.get("spanning_reads", 0))
    min_pairs = normalized.get("min_spanning_pairs", normalized.get("spanning_pairs", 0))
    normalized["min_spanning_reads"] = coerce_nonnegative_int(min_reads, default=0)
    normalized["min_spanning_pairs"] = coerce_nonnegative_int(min_pairs, default=0)
    return normalized


def normalize_dna_filter_keys(filters: dict | None) -> dict:
    """
    Placeholder DNA normalization path for shared workflow parity.
    Current behavior is passthrough to avoid functional changes.
    """
    return dict(filters or {})
