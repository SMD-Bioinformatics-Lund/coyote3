"""Atomic revision rotation for versioned clinical configuration documents."""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any

from pymongo.errors import OperationFailure

from api.contracts.operations import OperationResult

_TRANSACTIONS_UNSUPPORTED_CODES = frozenset({20, 263, 303})


def _rotate_without_transaction(
    collection: Any,
    *,
    active_selector: dict[str, Any],
    selector: dict[str, Any],
    expected_version: int,
    new_document: dict[str, Any],
    retire_fields: dict[str, Any],
) -> OperationResult:
    """Rotate a revision with a guarded write and compensating rollback."""
    retired = collection.update_one(
        active_selector,
        {"$set": {"is_active": False, **retire_fields}},
    )
    if retired.matched_count != 1:
        raise RuntimeError("Active configuration revision changed during update")
    try:
        inserted = collection.insert_one(new_document)
    except Exception:
        unset_fields = {key: "" for key in retire_fields}
        collection.update_one(
            {**selector, "version": expected_version, "is_active": False},
            {"$set": {"is_active": True}, "$unset": unset_fields},
        )
        raise
    return OperationResult(
        matched_count=1,
        modified_count=int(retired.modified_count or 0),
        inserted_count=1,
        requested_count=2,
        inserted_id=str(inserted.inserted_id),
    )


def rotate_active_revision(
    collection: Any,
    *,
    selector: dict[str, Any],
    expected_version: int,
    new_document: dict[str, Any],
    retire_fields: dict[str, Any],
) -> OperationResult:
    """Retire one expected active revision and insert its successor.

    MongoDB transactions are used when the deployment supports sessions. The
    guarded fallback is retained for lightweight standalone and test MongoDB
    deployments; it restores the prior active revision if insertion fails.
    """
    active_selector = {
        **selector,
        "is_active": True,
        "version": expected_version,
    }
    client = collection.database.client

    try:
        session_context = client.start_session()
    except (AttributeError, NotImplementedError, TypeError):
        session_context = nullcontext(None)

    with session_context as session:
        if session is not None:
            try:
                with session.start_transaction():
                    retired = collection.update_one(
                        active_selector,
                        {"$set": {"is_active": False, **retire_fields}},
                        session=session,
                    )
                    if retired.matched_count != 1:
                        raise RuntimeError("Active configuration revision changed during update")
                    inserted = collection.insert_one(new_document, session=session)
                return OperationResult(
                    matched_count=1,
                    modified_count=int(retired.modified_count or 0),
                    inserted_count=1,
                    requested_count=2,
                    inserted_id=str(inserted.inserted_id),
                )
            except OperationFailure as exc:
                if exc.code not in _TRANSACTIONS_UNSUPPORTED_CODES:
                    raise

        return _rotate_without_transaction(
            collection,
            active_selector=active_selector,
            selector=selector,
            expected_version=expected_version,
            new_document=new_document,
            retire_fields=retire_fields,
        )
