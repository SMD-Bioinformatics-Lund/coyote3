"""Atomic revision rotation for versioned clinical configuration documents."""

from __future__ import annotations

from typing import Any

from api.contracts.operations import OperationResult
from api.infra.mongo.transactions import run_transaction


def rotate_active_revision(
    collection: Any,
    *,
    selector: dict[str, Any],
    expected_version: int,
    new_document: dict[str, Any],
    retire_fields: dict[str, Any],
) -> OperationResult:
    """Retire one expected active revision and insert its successor in one transaction."""
    active_selector = {
        **selector,
        "is_active": True,
        "version": expected_version,
    }

    def rotate(session):
        """Retire the captured active revision and insert its successor.

        Args:
            session: Transaction session shared by both writes.

        Returns:
            Counts for the retirement and insertion, including the successor's ID.

        Raises:
            RuntimeError: If exactly one expected active revision was not matched.
        """
        retired = collection.update_one(
            active_selector,
            {"$set": {"is_active": False, **retire_fields}},
            session=session,
        )
        if retired.matched_count != 1:
            raise RuntimeError("Active configuration revision changed during update")
        inserted = collection.insert_one(dict(new_document), session=session)
        return OperationResult(
            matched_count=1,
            modified_count=int(retired.modified_count or 0),
            inserted_count=1,
            requested_count=2,
            inserted_id=str(inserted.inserted_id),
        )

    return run_transaction(collection.database.client, rotate)
