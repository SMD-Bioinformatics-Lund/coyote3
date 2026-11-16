# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Convert MongoDB driver write results into database-independent operation values."""

from typing import Any

from coyote.contracts.operations import OperationResult


def operation_from_update(result: Any, *, requested_count: int = 1) -> OperationResult:
    """Project a MongoDB update result into portable counts and string identities.

    Args:
        result: Driver result returned by an acknowledged update operation.
        requested_count: Number of requested records, defaulting to one.

    Returns:
        Operation outcome without a driver object or BSON identifier.
    """
    identifier = getattr(result, "upserted_id", None)
    return OperationResult(
        acknowledged=bool(getattr(result, "acknowledged", True)),
        matched_count=int(getattr(result, "matched_count", 0) or 0),
        modified_count=int(getattr(result, "modified_count", 0) or 0),
        requested_count=int(requested_count or 0),
        upserted_id=str(identifier) if identifier is not None else None,
    )


def operation_from_delete(result: Any, *, requested_count: int = 1) -> OperationResult:
    """Project a MongoDB deletion result into portable counts.

    Args:
        result: Driver result returned by a delete operation.
        requested_count: Number of requested records, defaulting to one.

    Returns:
        Database-independent deletion outcome.
    """
    return OperationResult(
        acknowledged=bool(getattr(result, "acknowledged", True)),
        deleted_count=int(getattr(result, "deleted_count", 0) or 0),
        requested_count=int(requested_count or 0),
    )


def operation_from_insert_one(result: Any) -> OperationResult:
    """Project a MongoDB insertion result into a portable count and string identity.

    Args:
        result: Driver result returned by a single-record insertion.

    Returns:
        Operation outcome without a driver-owned identifier.
    """
    acknowledged = bool(getattr(result, "acknowledged", True))
    identifier = getattr(result, "inserted_id", None)
    return OperationResult(
        acknowledged=acknowledged,
        inserted_count=int(acknowledged and identifier is not None),
        requested_count=1,
        inserted_id=str(identifier) if identifier is not None else None,
    )


def operation_from_insert_many(result: Any, *, requested_count: int = 0) -> OperationResult:
    """Project a MongoDB batch insertion result into portable counts.

    Args:
        result: Driver result returned by a batch insertion.
        requested_count: Requested batch size; zero uses the inserted count.

    Returns:
        Database-independent batch insertion outcome.
    """
    identifiers = list(getattr(result, "inserted_ids", []) or [])
    return OperationResult(
        acknowledged=bool(getattr(result, "acknowledged", True)),
        inserted_count=len(identifiers),
        requested_count=int(requested_count or len(identifiers)),
    )
