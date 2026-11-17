"""Metadata query contracts reject ambiguity and unsafe database syntax."""

from datetime import datetime, timezone

import pytest
from coyote.contracts.retrieval import ReadResource, ResourceReadQuery
from pydantic import ValidationError


@pytest.mark.parametrize(
    "payload",
    [
        {"filters": {"is_active": {"$ne": True}}},
        {"filters": {"is_active": {}}},
        {"filters": {"version": {"in": []}}},
        {"filters": {"version": {"in": [1] * 101}}},
        {"page": True},
        {"per_page": 201},
        {"descending": "false"},
        {"operation": "distinct"},
        {"field": "asp_id"},
        {"operation": "count", "fields": ["asp_id"]},
        {"operation": "ids", "sort": "asp_id"},
        {"fields": ["asp_id", "asp_id"]},
        {"include": ["assay", "assay"]},
        {"related_filters": {"users": {"username": "someone"}}},
        {"raw_query": {}},
    ],
)
def test_invalid_wire_options(payload):
    with pytest.raises(ValidationError):
        ResourceReadQuery.model_validate(payload)


@pytest.mark.parametrize(
    "resource,payload",
    [
        (ReadResource.ASP, {"filters": {"is_active": 1}}),
        (ReadResource.ASP, {"filters": {"version": True}}),
        (ReadResource.ASP, {"filters": {"version": "1"}}),
        (ReadResource.ASP, {"filters": {"is_active": {"gte": True}}}),
        (ReadResource.ASP, {"filters": {"asp_id": {"gte": "a"}}}),
        (ReadResource.ASP, {"filters": {"version": {"gte": 3, "lte": 2}}}),
        (ReadResource.ASP, {"fields": ["credentials"]}),
        (ReadResource.ASP, {"sort": "expected_files"}),
        (ReadResource.ISGL, {"include": ["assay"]}),
        (ReadResource.ASP, {"related_filters": {"assay": {"is_active": True}}}),
        (ReadResource.SAMPLES, {"related_filters": {"configuration": {"password": "secret"}}}),
        (ReadResource.SAMPLES, {"filters": {"time_added": "yesterday"}}),
    ],
)
def test_resource_types_and_field_allowlists(resource, payload):
    with pytest.raises(ValueError):
        ResourceReadQuery.model_validate(payload).validate_resource(resource)


def test_false_zero_null_membership_and_timestamp_are_preserved():
    query = ResourceReadQuery.model_validate(
        {
            "filters": {
                "reported": False,
                "version": 0,
                "diagnosis_id": None,
                "time_added": {"gte": "2026-01-01T00:00:00Z"},
                "asp_id": {"in": ["a", "b"]},
            }
        }
    ).validate_resource(ReadResource.SAMPLES)
    assert query.filters["reported"].eq is False
    assert query.filters["version"].eq == 0
    assert query.filters["diagnosis_id"].model_fields_set == {"eq"}
    assert query.filters["time_added"].gte == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert query.filters["asp_id"].one_of == ["a", "b"]
