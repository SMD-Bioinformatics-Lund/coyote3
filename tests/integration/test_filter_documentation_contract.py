"""Keep the canonical clinical-filter reference aligned with persisted schemas."""

import json
import re
from pathlib import Path
from typing import get_args

from coyote3.contracts.schemas.filter_profiles import (
    DnaFilterProfilesDoc,
    GermlineSnvFiltersDoc,
    RnaFilterProfilesDoc,
    SnvFiltersDoc,
)


def test_filter_reference_lists_current_profiles_and_snv_defaults() -> None:
    """Published filter paths and defaults must match the transport/persistence contract."""
    reference = Path("docs/reference/filter-profile-fields.md").read_text()
    profile_table = reference.split("## Profile structure", 1)[1].split("## SNV fields", 1)[0]
    documented_paths = set(re.findall(r"^\| `([^`]+)` \|", profile_table, re.MULTILINE))
    expected_paths = set()
    for model in (DnaFilterProfilesDoc, RnaFilterProfilesDoc):
        for intent, field in model.model_fields.items():
            profile = next(
                value for value in get_args(field.annotation) if hasattr(value, "model_fields")
            )
            expected_paths.update(f"{intent}.{analysis}" for analysis in profile.model_fields)
    assert documented_paths == expected_paths

    snv_table = reference.split("## SNV fields", 1)[1].split("## CNV fields", 1)[0]
    documented_defaults = {
        field: json.loads(default)
        for field, default in re.findall(
            r"^\| `([^`]+)` \|[^\n]+?\| `([^`]+)` \|", snv_table, re.MULTILINE
        )
    }
    assert set(documented_defaults) == set(SnvFiltersDoc.model_fields)
    for model in (SnvFiltersDoc, GermlineSnvFiltersDoc):
        for field, metadata in model.model_fields.items():
            assert documented_defaults[field] == metadata.get_default(call_default_factory=True)
