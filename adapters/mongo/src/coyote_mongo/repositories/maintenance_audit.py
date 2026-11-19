# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Durable intent and outcome receipts for MongoDB operations outside transactions."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import uuid4

from coyote_mongo.config.settings import AuditContext
from coyote_mongo.repositories.audit_outbox import enqueue_audit
from coyote_mongo.transactions import run_transaction


@contextmanager
def audit_maintenance(
    database: Any, *, context: AuditContext, operation: str, resource: str
) -> Iterator[None]:
    """Journal a namespace operation that MongoDB cannot include in a transaction.

    The intent must commit before the operation starts. The outcome is a separate
    receipt, sharing the operation ID. An intent without an outcome requires
    inspection; it never establishes success or automatic rollback. Exceptions
    record only their type, not potentially sensitive driver diagnostics.
    """
    operation_id = str(uuid4())

    def receipt(outcome: str, error: str | None = None) -> None:
        run_transaction(
            database.client,
            lambda session: enqueue_audit(
                database,
                session,
                context=context,
                event_type=f"maintenance.{outcome}",
                resource_type=resource,
                resource_id=operation_id,
                actor="system",
                outcome={"started": "pending", "failed": "failure", "completed": "success"}[
                    outcome
                ],
                metadata={"operation": operation, "error_type": error},
            ),
        )

    receipt("started")
    try:
        yield
    except Exception as exc:
        receipt("failed", type(exc).__name__)
        raise
    else:
        receipt("completed")
