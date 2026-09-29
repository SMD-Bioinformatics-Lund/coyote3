"""Report save preconditions include clinical inputs and rule provenance."""

from copy import deepcopy

import pytest

from api.application.reporting.preview_consistency import (
    preview_fingerprint,
    require_current_preview,
)
from api.domain.core.exceptions import AppError


def test_generation_metadata_does_not_change_reviewed_content():
    context = {
        "sample": {"name": "SYNTHETIC"},
        "save": False,
        "report_date": "first",
        "report_timestamp": "first",
    }
    fingerprint = preview_fingerprint("dna", context)
    require_current_preview(
        fingerprint, "dna", dict(context, save=True, report_date="later", report_timestamp="later")
    )


@pytest.mark.parametrize(
    "key",
    [
        "sample",
        "assay_config",
        "clinical_rule_evaluation",
        "report_sections_data",
        "latest_sample_comment_text",
    ],
)
def test_changes_require_a_new_preview(key):
    context = {key: {"value": "reviewed"}}
    expected = preview_fingerprint("dna", context)
    changed = deepcopy(context)
    changed[key] = {"value": "changed"}
    with pytest.raises(AppError, match="Refresh and review") as error:
        require_current_preview(expected, "dna", changed)
    assert error.value.status_code == 409


def test_template_change_requires_a_new_preview():
    with pytest.raises(AppError):
        require_current_preview(preview_fingerprint("dna", {}), "rna", {})
