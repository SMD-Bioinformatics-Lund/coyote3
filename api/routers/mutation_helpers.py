"""Shared helpers for mutation-style API endpoints."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from api.extensions import util
from api.security.access import ApiUser


def run_serialized_mutation(
    *,
    sample_id: str,
    user: ApiUser,
    validate: Callable[[], Any],
    mutate: Callable[[], None],
    payload: Callable[[], dict[str, Any]],
    util_module: Any = util,
) -> dict[str, Any]:
    """Validate access, run mutation, and serialize the canonical response payload."""
    _ = sample_id
    _ = user
    validate()
    mutate()
    return util_module.common.convert_to_serializable(payload())
