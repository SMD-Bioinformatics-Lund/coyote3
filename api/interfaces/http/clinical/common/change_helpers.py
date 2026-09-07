"""Common helpers for change-style API endpoints."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from api.app.container import util
from api.application.common.change_payload import change_payload
from api.contracts.operations import OperationResult
from api.security.access import ApiUser


def resource_change(
    sample_id: str,
    resource_id: str,
    user: ApiUser,
    service: Any,
    *,
    resource: str,
    action: str,
    mutate: Callable[[], Any],
    validate: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Generic resource mutation: validate, mutate, return canonical payload.

    Works for CNVs, fusions, translocations, and similar resources where the
    validate step is ``_get_sample_for_api(sample_id, user)``.
    """
    from api.security.access import _get_sample_for_api

    return run_serialized_change(
        sample_id=sample_id,
        user=user,
        validate=validate or (lambda: _get_sample_for_api(sample_id, user)),
        mutate=mutate,
        payload=lambda: change_payload(
            sample_id=sample_id,
            resource=resource,
            resource_id=resource_id,
            action=action,
        ),
        util_module=util,
    )


def comment_change(
    sample_id: str,
    resource_id: str,
    comment_id: str,
    user: ApiUser,
    service: Any,
    *,
    resource: str,
    action: str,
    mutate: Callable[[], Any],
    validate: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Generic comment visibility mutation for any resource type."""
    from api.security.access import _get_sample_for_api

    return run_serialized_change(
        sample_id=sample_id,
        user=user,
        validate=validate or (lambda: _get_sample_for_api(sample_id, user)),
        mutate=mutate,
        payload=lambda: change_payload(
            sample_id=sample_id,
            resource=resource,
            resource_id=comment_id,
            action=action,
        ),
        util_module=util,
    )


def run_serialized_change(
    *,
    sample_id: str,
    user: ApiUser,
    validate: Callable[[], Any],
    mutate: Callable[[], Any],
    payload: Callable[[], dict[str, Any]],
    util_module: Any = util,
) -> dict[str, Any]:
    """Validate access, run mutation, and serialize the canonical response payload."""
    _ = sample_id
    _ = user
    validate()
    operation = mutate()
    response = payload()
    if isinstance(operation, OperationResult):
        response.setdefault("meta", {})["operation"] = operation.to_dict()
    return util_module.common.convert_to_serializable(response)
