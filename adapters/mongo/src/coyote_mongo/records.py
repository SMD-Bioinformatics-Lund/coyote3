# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Project stored findings into application records with canonical string identities."""

from datetime import timezone
from typing import Any

from bson import ObjectId, json_util
from coyote.domain.record_identity import RecordIdentity
from pydantic import BaseModel

_UTC_JSON = json_util.JSONOptions(tz_aware=True, tzinfo=timezone.utc)


def application_record(value: Any) -> Any:
    """Copy records while removing provider-specific identity objects.

    Args:
        value: A finding, nested annotation/comment, scalar or absent record.

    Returns:
        Independent dictionaries/lists with ObjectId values represented as strings.
        Extended JSON date and identity wrappers are decoded at this adapter boundary.
        Clinical field names, nulls, timestamps and numeric values are preserved.
    """
    if isinstance(value, ObjectId):
        return RecordIdentity(str(value))
    if isinstance(value, dict):
        if set(value) in ({"$date"}, {"$oid"}):
            wrapper = {
                key: json_util.object_hook(item, json_options=_UTC_JSON)
                if isinstance(item, dict)
                else item
                for key, item in value.items()
            }
            return application_record(json_util.object_hook(wrapper, json_options=_UTC_JSON))
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


def storage_record(value: Any) -> Any:
    """Restore native identities when portable records return to this MongoDB host.

    Args:
        value: Application record containing explicitly typed identity strings.

    Returns:
        Independent provider record. Ordinary text is never interpreted as an identity.

    Raises:
        ValueError: A typed identity cannot be represented by this MongoDB host.
    """
    if isinstance(value, RecordIdentity):
        return ObjectId(value)
    if isinstance(value, dict):
        return {key: storage_record(item) for key, item in value.items()}
    if isinstance(value, list):
        return [storage_record(item) for item in value]
    if isinstance(value, tuple):
        return tuple(storage_record(item) for item in value)
    return value
