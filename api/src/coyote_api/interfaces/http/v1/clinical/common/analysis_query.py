# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Translate HTTP query values into application-owned analysis inputs."""

from coyote.application.common.analysis_query import AnalysisQuery
from coyote.domain.common.coercion import coerce_bool
from fastapi import Request


def bulk_flag_values(payload: dict, resource_ids: list[str], apply: bool) -> tuple[list[str], bool]:
    """Adapt established JSON/query flag inputs to explicit SDK identifiers and a boolean.

    Args:
        payload: Optional JSON object with resource_ids, the existing variant_ids spelling, and apply.
        resource_ids: Query-supplied identifiers when neither JSON identifier value is a list.
        apply: Query-supplied boolean used when the JSON value has no supported representation.

    Returns:
        Selected identifiers and the existing boolean conversion result.
    """
    values = payload if isinstance(payload, dict) else {}
    if isinstance(values.get("resource_ids"), list):
        resource_ids = values["resource_ids"]
    elif isinstance(values.get("variant_ids"), list):
        resource_ids = values["variant_ids"]
    return resource_ids, coerce_bool(values.get("apply"), default=apply)


def analysis_query_from_request(request: Request) -> AnalysisQuery:
    """Copy the finding-query values consumed by application workflows.

    Args:
        request: HTTP request containing search, sort, page and analysis-intent values.

    Returns:
        Explicit application input. Duplicate scalar keys retain Starlette's last-value behavior.
    """
    return AnalysisQuery(parameters=dict(request.query_params), source_path=request.url.path)
