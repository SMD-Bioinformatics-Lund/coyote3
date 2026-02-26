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

"""Backward-compatible wrappers for DNA CNV query builders."""

from __future__ import annotations

from coyote.services.dna.cnvqueries import build_cnv_query as service_build_cnv_query


def build_cnv_query(sample_id: str, filters: dict) -> dict:
    """Delegate to service-level CNV query builder."""
    return service_build_cnv_query(sample_id, filters)
