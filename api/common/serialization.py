"""Shared serialization helpers used by utility/service layers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any, Dict, Tuple

from bson import ObjectId
from pydantic import BaseModel


def convert_object_id(data: Any) -> list | dict | str | Any:
    """Recursively convert ObjectId values to strings."""
    if isinstance(data, list):
        return [convert_object_id(item) for item in data]
    if isinstance(data, dict):
        return {key: convert_object_id(value) for key, value in data.items()}
    if isinstance(data, ObjectId):
        return str(data)
    return data


def convert_to_serializable(data: Any) -> list | dict | str | Any:
    """Recursively convert common non-JSON types into JSON-safe values."""
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
    """Convert a dictionary to a deterministic tuple of key/value pairs."""
    return tuple(sorted(d.items()))


def tuple_to_dict(t: Tuple) -> Dict:
    """Convert tuple key/value pairs into a dictionary."""
    return dict(t)


def safe_json_load(data: Any, fallback=None) -> dict:
    """Attempt to load JSON and return fallback on parse errors."""
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return fallback or {}
