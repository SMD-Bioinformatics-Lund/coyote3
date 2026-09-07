"""Common change response builder used across all variant/resource services."""

from __future__ import annotations

from typing import Any

from api.contracts.operations import OperationResult


def change_payload(
    *,
    sample_id: str,
    resource: str,
    resource_id: str,
    action: str,
    operation: OperationResult | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the standard change response payload.

    Args:
        sample_id: Sample identifier tied to the mutation.
        resource: Resource type being changed.
        resource_id: Identifier of the mutated resource.
        action: Mutation verb reported to the client.
        operation: Optional structured mutation metadata.

    Returns:
        dict[str, Any]: Normalized change response body.
    """
    meta: dict[str, Any] = {"status": "updated"}
    if isinstance(operation, OperationResult):
        meta["operation"] = operation.to_dict()
    elif isinstance(operation, dict):
        meta["operation"] = operation

    return {
        "status": "ok",
        "sample_id": str(sample_id),
        "resource": resource,
        "resource_id": str(resource_id),
        "action": action,
        "meta": meta,
    }
