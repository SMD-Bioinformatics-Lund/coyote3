"""Common serialization helpers used by utility/service layers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any, Dict, Tuple

from bson import ObjectId
from pydantic import BaseModel


def convert_object_id(data: Any) -> list | dict | str | Any:
    """Recursively convert ObjectId values in lists and dictionaries to strings.

    Args:
        data: Scalar or nested list/dictionary; dictionary keys are left untouched.

    Returns:
        New lists and dictionaries with ObjectId values stringified. Other values,
        including None and tuples, pass through unchanged. Inputs are not mutated.
    """
    if isinstance(data, list):
        return [convert_object_id(item) for item in data]
    if isinstance(data, dict):
        return {key: convert_object_id(value) for key, value in data.items()}
    if isinstance(data, ObjectId):
        return str(data)
    return data


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


def dict_to_tuple(d: Dict) -> Tuple:
    """Sort dictionary entries by key and retain them in a tuple.

    Args:
        d: Dictionary with mutually comparable keys.

    Returns:
        A tuple of key/value pairs. Values remain shared and are not converted;
        the result is hashable only when its keys and values are hashable.

    Raises:
        TypeError: Keys cannot be compared for sorting.
    """
    return tuple(sorted(d.items()))


def tuple_to_dict(t: Tuple) -> Dict:
    """Build a dictionary from key/value pairs without copying their values.

    Args:
        t: Iterable of two-element pairs with hashable keys.

    Returns:
        A new dictionary; later duplicate keys overwrite earlier values.

    Raises:
        TypeError: The input is not iterable or a key is unhashable.
        ValueError: An entry does not contain exactly two elements.
    """
    return dict(t)


def safe_json_load(data: Any, fallback=None) -> dict:
    """Decode JSON, substituting a truthy fallback on JSON syntax errors only.

    Args:
        data: JSON text as str, bytes, or bytearray; None is not accepted.
        fallback: Value to return on JSONDecodeError if truthy. None or any other
            falsy value selects a new empty dictionary.

    Returns:
        The decoded value, which may be a list, scalar, or None, not just a dict.
        On syntax errors, returns fallback itself when truthy, otherwise {}.

    Raises:
        TypeError: data is not str, bytes, or bytearray.
        UnicodeDecodeError: Byte input cannot be decoded as JSON text.
    """
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return fallback or {}
