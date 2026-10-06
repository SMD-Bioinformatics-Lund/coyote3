"""Keep private authoring experiments outside the committed operational toolset."""

import pytest

from scripts.quality.check_staged_sensitive_data import _find_violations


@pytest.mark.parametrize(
    "path",
    [
        ".design/render_diagrams.py",
        ".design/definitions.json",
        ".design/preview.svg",
        ".design/one-off-cleanups/repair.py",
        "frontend/.design/layout.js",
    ],
)
def test_design_scratch_is_rejected_before_binary_exemptions(path):
    assert _find_violations(path, b"synthetic content") == [
        "private design scratch file; commit the reviewed deliverable instead"
    ]


@pytest.mark.parametrize(
    "path",
    [
        "docs/assets/diagrams/clinical-flow.svg",
        "scripts/docs/export_collection_contracts_doc.py",
        "docs/development/writing-documentation.md",
    ],
)
def test_reviewed_artifacts_and_reproducible_tools_remain_allowed(path):
    assert _find_violations(path, b"synthetic content") == []
