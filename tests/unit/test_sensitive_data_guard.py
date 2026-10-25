"""Missing YAML identifiers are safe; literal or unmarked identifier strings are rejected."""

import pytest

from scripts.quality.check_staged_sensitive_data import _find_violations


@pytest.mark.parametrize("value", ["null", "NULL", "~", "null # no control", "~ # no control"])
def test_absent_yaml_identifier_is_not_sensitive(value):
    """YAML null values preserve optional fixture fields without inventing identifiers."""
    content = f"name: SYNTHETIC_SAMPLE\ncontrol_id: {value}\n".encode()
    assert _find_violations("tests/fixtures/synthetic.yaml", content) == []


@pytest.mark.parametrize("value", ["'null'", '"null"', "null suffix", "private-control", "~suffix"])
def test_literal_yaml_identifier_still_requires_a_synthetic_marker(value):
    """Quoted null, non-null scalars and unmarked identifiers retain the existing rejection."""
    content = f"name: SYNTHETIC_SAMPLE\ncontrol_id: {value}\n".encode()
    assert any(
        "non-synthetic sample metadata" in violation
        for violation in _find_violations("tests/fixtures/synthetic.yaml", content)
    )
