"""Capture published finding-selection policies for one report execution."""

import hashlib
import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from coyote3.contracts.schemas.query_rules import (
    QueryRuleResolution,
    QueryRuleScope,
)

_report_policies: ContextVar[dict[str, QueryRuleResolution] | None] = ContextVar(
    "report_query_policies", default=None
)


@contextmanager
def capture_query_policies() -> Iterator[dict[str, QueryRuleResolution]]:
    """Capture and reuse each scoped publication during one report build.

    Yields:
        Exact resolved policies used by finding queries in this execution context.
    """
    policies: dict[str, QueryRuleResolution] = {}
    token = _report_policies.set(policies)
    try:
        yield policies
    finally:
        _report_policies.reset(token)


def resolved_policy_snapshot(
    scope: QueryRuleScope, resolver: Callable[[QueryRuleScope], QueryRuleResolution]
) -> QueryRuleResolution:
    """Resolve live rules once per scope within a report, recording their exact lineage.

    Args:
        scope: Complete sample query scope.
        resolver: Published-policy resolver; drafts are excluded by its repository.

    Returns:
        Current resolution, reused only inside the active report build.
    """
    policies = _report_policies.get()
    if policies is None:
        return resolver(scope)
    key = scope.key()
    if key not in policies:
        policies[key] = resolver(scope)
    return policies[key]


def query_policies_hash(policies: dict[str, Any]) -> str:
    """Hash canonical effective policy content and its exact source lineage.

    Args:
        policies: JSON-compatible resolution documents keyed by complete query scope.

    Returns:
        SHA-256 digest independent of dictionary insertion order.
    """
    return hashlib.sha256(
        json.dumps(policies, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
