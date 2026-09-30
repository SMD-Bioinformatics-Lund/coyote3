"""Serialize API payloads without mutating their source models."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from bson import ObjectId
from pydantic import BaseModel


def convert_to_serializable(data: Any) -> list | dict | str | Any:
    """Convert supported models and containers to plain values recursively.

    Args:
        data: Value to process. Pydantic models use model_dump; other types with
            a callable dict method defined on their class use that method.

    Returns:
        Strings for ObjectIds and ISO strings for dates/datetimes; dictionaries
        for models/mappings, converting both keys and values; lists for lists,
        tuples, and sets. Unsupported values and None pass through unchanged,
        so arbitrary inputs are not guaranteed to be JSON-serializable.

    Notes:
        Rebuilds containers without mutating them. Custom dict methods are invoked
        and their errors propagate. Set iteration does not guarantee output order.
    """
    if isinstance(data, ObjectId):
        return str(data)

    if isinstance(data, (datetime, date)):
        return data.isoformat()

    if isinstance(data, BaseModel):
        return convert_to_serializable(data.model_dump())

    dict_method = getattr(type(data), "dict", None)
    if callable(dict_method):
        return convert_to_serializable(data.dict())

    if isinstance(data, Mapping):
        return {convert_to_serializable(k): convert_to_serializable(v) for k, v in data.items()}

    if isinstance(data, (list, tuple, set)):
        return [convert_to_serializable(item) for item in data]

    return data
