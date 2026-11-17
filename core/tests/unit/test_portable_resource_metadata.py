"""Permitted metadata remains strict and excludes undeclared fields."""

from typing import get_args

import pytest
from coyote.contracts import resource_fields
from coyote.contracts.resource_metadata import (
    AssayMetadata,
    ConfigurationMetadata,
    DiagnosisMetadata,
    GeneListMetadata,
    GroupMetadata,
    SampleMetadata,
)
from pydantic import ValidationError

pytestmark = pytest.mark.unit


def test_absent_metadata_stays_null_and_read_only() -> None:
    metadata = AssayMetadata(asp_id="assay-a", is_active=False, version=0)
    assert metadata.display_name is None
    assert metadata.is_active is False
    assert metadata.version == 0
    with pytest.raises(ValidationError, match="frozen"):
        metadata.asp_id = "assay-b"


def test_unknown_or_coerced_response_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        SampleMetadata(name="SYNTHETIC", patient_name="not permitted")
    with pytest.raises(ValidationError):
        AssayMetadata(is_active="true")


@pytest.mark.parametrize(
    "fields,metadata",
    [
        (resource_fields.SampleField, SampleMetadata),
        (resource_fields.AssayField, AssayMetadata),
        (resource_fields.ConfigurationField, ConfigurationMetadata),
        (resource_fields.DiagnosisField, DiagnosisMetadata),
        (resource_fields.GroupField, GroupMetadata),
        (resource_fields.GeneListField, GeneListMetadata),
    ],
)
def test_selectable_metadata_keys_match_response_contract(fields, metadata) -> None:
    assert set(get_args(fields)) == set(metadata.model_fields)
