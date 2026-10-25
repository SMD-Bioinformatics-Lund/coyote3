"""Project stored findings into application records with canonical string identities."""

from typing import Any

from bson import ObjectId
from pydantic import BaseModel


def application_record(value: Any) -> Any:
    """Copy records while removing provider-specific identity objects.

    Args:
        value: A finding, nested annotation/comment, scalar or absent record.

    Returns:
        Independent dictionaries/lists with ObjectId values represented as strings.
        Clinical field names, nulls, timestamps and numeric values are preserved.
    """
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, dict):
        return {key: application_record(item) for key, item in value.items()}
    if isinstance(value, list):
        return [application_record(item) for item in value]
    if isinstance(value, tuple):
        return tuple(application_record(item) for item in value)
    return value


def application_result(value: Any) -> Any:
    """Detach completed SDK values without changing canonical service inputs.

    Args:
        value: Completed application value, including nested Pydantic result models.

    Returns:
        The same result shape and model types with native identifiers represented
        as strings. Persisted release content must be validated before this projection.
    """
    if isinstance(value, BaseModel):
        return value.model_copy(
            update={
                key: application_result(getattr(value, key))
                for key in (*type(value).model_fields, *(value.model_extra or {}))
            },
            deep=True,
        )
    if isinstance(value, dict):
        return {key: application_result(item) for key, item in value.items()}
    if isinstance(value, list):
        return [application_result(item) for item in value]
    if isinstance(value, tuple):
        return tuple(application_result(item) for item in value)
    return application_record(value)
