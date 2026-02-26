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


from typing import Any, Dict

from coyote.services.rna.fusion_query_builder import (
    build_fusion_query as service_build_fusion_query,
    build_fusion_optional_filters as service_build_fusion_optional_filters,
)

def _coerce_nonnegative_int(value: Any, default: int = 0) -> int:
    """
    Deprecated local helper retained for backward compatibility.
    """
    from coyote.services.workflow.filter_normalization import coerce_nonnegative_int

    return coerce_nonnegative_int(value, default)


def build_fusion_query(assay_group: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Backward-compatible wrapper delegating to service-level query builder.
    """
    return service_build_fusion_query(assay_group, settings)


def build_fusion_optional_filters(settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Backward-compatible wrapper delegating to service-level query builder.
    """
    return service_build_fusion_optional_filters(settings)
