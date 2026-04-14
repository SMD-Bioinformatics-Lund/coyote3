"""Mongo-specific persistence helpers shared across backend workflows."""

from __future__ import annotations

from typing import Any

from bson.objectid import ObjectId
from pymongo.errors import BulkWriteError, DuplicateKeyError


def to_provider_id(value: str) -> Any:
    """Convert an app-layer id into a provider-native id when possible."""
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    return value


def new_object_id() -> ObjectId:
    """Return a new provider-native object id."""
    return ObjectId()


def new_object_id_str() -> str:
    """Return a new provider-native object id serialized as a string."""
    return str(ObjectId())


def insert_one_document(
    collection,
    document: dict[str, Any],
    *,
    ignore_duplicate: bool = False,
    session: Any | None = None,
) -> str | None:
    """Insert one document and optionally suppress duplicate-key errors."""
    try:
        kwargs = {"session": session} if session is not None else {}
        result = collection.insert_one(dict(document), **kwargs)
    except DuplicateKeyError:
        if not ignore_duplicate:
            raise
        return None
    return str(result.inserted_id)


def insert_many_documents(
    collection,
    documents: list[dict[str, Any]],
    *,
    ignore_duplicates: bool = False,
    session: Any | None = None,
) -> int:
    """Insert many documents and optionally suppress duplicate-key-only errors."""
    try:
        kwargs = {"session": session} if session is not None else {}
        result = collection.insert_many([dict(doc) for doc in documents], ordered=False, **kwargs)
        return len(result.inserted_ids)
    except BulkWriteError as exc:
        if not ignore_duplicates:
            raise
        details = exc.details or {}
        inserted_count = int(details.get("nInserted", 0))
        write_errors = details.get("writeErrors", []) or []
        non_duplicate_errors = [err for err in write_errors if err.get("code") != 11000]
        if non_duplicate_errors:
            raise
        return inserted_count
