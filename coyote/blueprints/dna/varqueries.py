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

"""Backward-compatible wrappers for DNA SNV query builders."""

from __future__ import annotations

from coyote.services.dna.varqueries import (
    build_pos_genes_filter as service_build_pos_genes_filter,
    build_query as service_build_query,
)


def build_query(assay_group: str, settings: dict) -> dict:
    """Delegate to service-level SNV query builder."""
    return service_build_query(assay_group, settings)


def build_pos_genes_filter(settings: dict) -> dict:
    """Delegate to service-level gene/POS filter helper."""
    return service_build_pos_genes_filter(settings)
