# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Atomic revision rotation for versioned clinical configuration documents."""

from __future__ import annotations

from typing import Any

from coyote.contracts.operations import OperationResult

from coyote_mongo.config.settings import AuditContext
from coyote_mongo.repositories.audit_outbox import enqueue_audit
from coyote_mongo.transactions import run_transaction


def rotate_active_revision(
    collection: Any,
    *,
    context: AuditContext,
    selector: dict[str, Any],
    expected_version: int,
    new_document: dict[str, Any],
    retire_fields: dict[str, Any],
) -> OperationResult:
    """Retire one expected active revision and insert its successor atomically.

    Args:
        collection: Configuration collection owning both revision writes.
        context: Explicit deployment identity for the committed audit receipt.
        selector: Business scope identifying the active revision.
        expected_version: Revision number that must still be active.
        new_document: Validated successor document to insert.
        retire_fields: Retirement metadata applied to the expected predecessor.

    Returns:
        Portable counts and identity for the atomic retirement and insertion.

    Raises:
        RuntimeError: The expected active revision changed before retirement.
    """
    return run_transaction(
        collection.database.client,
        lambda session: rotate_in_session(
            collection,
            session=session,
            context=context,
            selector=selector,
            expected_version=expected_version,
            new_document=new_document,
            retire_fields=retire_fields,
        ),
    )


def rotate_in_session(
    collection: Any,
    *,
    session: Any,
    context: AuditContext,
    selector: dict,
    expected_version: int,
    new_document: dict,
    retire_fields: dict,
) -> OperationResult:
    """Retire the expected active revision, insert its successor and audit both in one session."""
    active_selector = {**selector, "is_active": True, "version": expected_version}
    retired = collection.update_one(
        active_selector,
        {"$set": {"is_active": False, **retire_fields}},
        session=session,
    )
    if retired.matched_count != 1:
        raise RuntimeError("Active configuration revision changed during update")
    inserted = collection.insert_one(dict(new_document), session=session)
    enqueue_audit(
        collection.database,
        session,
        context=context,
        event_type="configuration.revision_rotated",
        resource_type=collection.name,
        resource_id=inserted.inserted_id,
        actor=new_document.get("updated_by"),
        metadata={"previous_version": expected_version, "version": new_document.get("version")},
    )
    return OperationResult(
        matched_count=1,
        modified_count=int(retired.modified_count or 0),
        inserted_count=1,
        requested_count=2,
        inserted_id=str(inserted.inserted_id),
    )
