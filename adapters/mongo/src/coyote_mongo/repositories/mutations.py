# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Data writes whose audit receipt shares the owning MongoDB transaction."""

from collections.abc import Mapping
from typing import Any, Literal

from bson import ObjectId
from pymongo.client_session import ClientSession

from coyote_mongo.config.settings import AuditContext
from coyote_mongo.repositories.audit_outbox import enqueue_audit
from coyote_mongo.transactions import run_transaction

WriteOperation = Literal[
    "insert_one",
    "insert_many",
    "update_one",
    "update_many",
    "replace_one",
    "delete_one",
    "delete_many",
    "find_one_and_update",
    "find_one_and_delete",
    "find_one_and_replace",
    "bulk_write",
]
_OPERATIONS = {
    "insert_one",
    "insert_many",
    "update_one",
    "update_many",
    "replace_one",
    "delete_one",
    "delete_many",
    "find_one_and_update",
    "find_one_and_delete",
    "find_one_and_replace",
    "bulk_write",
}


def write_with_audit(
    collection: Any,
    operation: WriteOperation,
    *args: Any,
    context: AuditContext,
    session: ClientSession | None = None,
    record_ids: bool = True,
    actor: str | None = None,
    **options: Any,
) -> Any:
    """Commit a mutation and its bounded receipt, or join an existing transaction.

    Args:
        collection: Owning data collection, never the audit transport itself.
        operation: Supported PyMongo write method.
        *args: Positional arguments for that method. Values are never copied to audit.
        context: Explicit deployment identity and audit destination.
        session: Owning active transaction. None creates a required transaction.
        record_ids: False for credential stores, whose keys may contain token hashes.
        actor: Verified actor for authentication or background operations.
        **options: Driver options other than the owning session.

    Returns:
        The original driver result after commit, or within the supplied transaction.

    Raises:
        ValueError: The operation or supplied transaction is invalid.
        PyMongoError: Either the data mutation or receipt fails; both must roll back.

    Notes:
        Captures operation, counts, field names and at most 50 document identifiers.
        It never captures query values, document bodies, credentials or clinical text.
        Business-level receipts remain distinct from these persistence receipts.
    """
    if operation not in _OPERATIONS:
        raise ValueError("Unsupported audited data operation")
    if not isinstance(context, AuditContext):
        raise ValueError("Data mutations require an explicit audit context")
    if session is not None and (
        not session.in_transaction or session.client is not collection.database.client
    ):
        raise ValueError("Data mutation requires the owning client's active transaction")
    arguments = list(args)
    # Materialize generators and identities once so a transaction retry is repeatable.
    if operation in {"insert_one", "insert_many"}:
        documents = [arguments[0]] if operation == "insert_one" else list(arguments[0])
        for document in documents:
            document.setdefault("_id", ObjectId())
        arguments[0] = documents[0] if operation == "insert_one" else documents
    elif operation == "bulk_write":
        arguments[0] = list(arguments[0])

    def change(active_session: ClientSession) -> Any:
        identifiers = []
        if record_ids and operation not in {"insert_one", "insert_many", "bulk_write"}:
            limit = 51 if operation in {"update_many", "delete_many"} else 1
            read_options = {
                name: options[name] for name in ("collation", "hint") if name in options
            }
            candidates = collection.find(
                arguments[0], {"_id": 1}, session=active_session, **read_options
            )
            if options.get("sort"):
                candidates = candidates.sort(options["sort"])
            identifiers = [row["_id"] for row in candidates.limit(limit)]
        result = getattr(collection, operation)(*arguments, session=active_session, **options)
        counts: dict[str, int] = {}
        if operation == "insert_one":
            counts["inserted"] = 1
            identifiers = [result.inserted_id]
        elif operation == "insert_many":
            counts["inserted"] = len(result.inserted_ids)
            identifiers = list(result.inserted_ids[:51])
        elif operation.startswith("find_one_and_"):
            counts["deleted" if operation == "find_one_and_delete" else "written"] = int(
                result is not None or bool(options.get("upsert"))
            )
            if isinstance(result, Mapping) and "_id" in result:
                identifiers = [result["_id"]]
        else:
            for name in ("matched", "modified", "deleted", "inserted", "upserted"):
                value = getattr(result, f"{name}_count", None)
                if isinstance(value, int):
                    counts[name] = value
            upserted_id = getattr(result, "upserted_id", None)
            if upserted_id is not None:
                counts["upserted"] = 1
                identifiers.append(upserted_id)
        changed = any(value for name, value in counts.items() if name != "matched")
        if changed:
            metadata: dict[str, Any] = {"operation": operation, "counts": counts}
            if record_ids:
                metadata["document_ids"] = [str(value) for value in identifiers[:50]]
                metadata["document_ids_truncated"] = (
                    len(identifiers) > 50 or operation == "bulk_write" or not identifiers
                )
            if len(arguments) > 1 and isinstance(arguments[1], Mapping):
                update = arguments[1]
                metadata["fields"] = sorted(
                    {
                        str(field)
                        for key, value in update.items()
                        for field in (
                            value if key.startswith("$") and isinstance(value, Mapping) else [key]
                        )
                    }
                )[:50]
            enqueue_audit(
                collection.database,
                active_session,
                context=context,
                event_type=f"database.{operation}",
                category="database_mutation",
                resource_type=collection.name,
                actor=actor,
                resource_id=str(identifiers[0])
                if record_ids and len(identifiers) == 1
                else str(ObjectId()),
                metadata=metadata,
            )
        return result

    if session is not None:
        try:
            return change(session)
        except BaseException:
            # A repository may translate the exception into a failed result. Do
            # not let that caller subsequently commit a write without its receipt.
            if session.in_transaction:
                session.abort_transaction()
            raise
    return run_transaction(collection.database.client, change)
