"""Reject ambiguous selection and retain explicit pipeline classification."""

import pytest

from coyote3.application.ingest.parsers import (
    DnaIngestParser,
    _normalize_callers_field,
    _normalize_fusion_docs,
)


def test_fractional_fusion_selection_is_not_truncated():
    """Only explicit binary selection states are accepted."""
    with pytest.raises(ValueError, match="selected"):
        _normalize_fusion_docs([{"genes": "SYNTHETIC", "calls": [{"selected": 1.5}]}])


def test_symbolic_amplification_is_not_reclassified_as_duplication():
    """An explicit AMP label supplies the type when type was omitted."""
    assert DnaIngestParser._parse_cnvs_only([{"ratio": "AMP"}])[0]["type"] == "AMP"


def test_null_caller_entries_are_not_named_callers():
    """Sparse caller lists omit null values rather than producing a caller named none."""
    assert _normalize_callers_field([None, "SYNTHETIC"]) == ["synthetic"]


@pytest.mark.parametrize(
    "payload", [[{"ratio": 0.5}, None], {"valid": {"ratio": 0.5}, "invalid": []}]
)
def test_cnv_import_does_not_silently_drop_invalid_rows(payload):
    """Malformed rows must reject the bundle instead of producing a partial sample."""
    with pytest.raises(ValueError, match="objects"):
        DnaIngestParser._parse_cnvs_only(payload)
