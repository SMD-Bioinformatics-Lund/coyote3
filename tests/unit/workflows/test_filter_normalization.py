"""Tests for workflow filter normalization helpers."""

from __future__ import annotations

from api.core.workflows import filter_normalization as norm


def test_coerce_nonnegative_int_handles_valid_invalid_and_negative_values():
    """Handle test coerce nonnegative int handles valid invalid and negative values.

    Returns:
        The function result.
    """
    assert norm.coerce_nonnegative_int("5") == 5
    assert norm.coerce_nonnegative_int(3) == 3
    assert norm.coerce_nonnegative_int("-1", default=7) == 7
    assert norm.coerce_nonnegative_int(None, default=9) == 9
    assert norm.coerce_nonnegative_int("bad", default=11) == 11


def test_normalize_rna_filter_keys_uses_canonical_fields_and_preserves_other_keys():
    """Handle test normalize rna filter keys uses canonical fields and preserves other keys.

    Returns:
        The function result.
    """
    payload = {"spanning_reads": "4", "spanning_pairs": "2", "label": "rna"}

    normalized = norm.normalize_rna_filter_keys(payload)

    assert normalized["min_spanning_reads"] == 4
    assert normalized["min_spanning_pairs"] == 2
    assert normalized["label"] == "rna"
    assert payload.get("min_spanning_reads") is None


def test_normalize_rna_filter_keys_prefers_min_keys_when_present():
    """Handle test normalize rna filter keys prefers min keys when present.

    Returns:
        The function result.
    """
    payload = {"min_spanning_reads": "8", "spanning_reads": "2", "min_spanning_pairs": 3}

    normalized = norm.normalize_rna_filter_keys(payload)

    assert normalized["min_spanning_reads"] == 8
    assert normalized["min_spanning_pairs"] == 3


def test_normalize_dna_filter_keys_returns_copy():
    """Handle test normalize dna filter keys returns copy.

    Returns:
        The function result.
    """
    payload = {"min_alt_reads": 5}

    normalized = norm.normalize_dna_filter_keys(payload)

    assert normalized["min_alt_reads"] == 5
    assert normalized["vep_consequences"] == []
    assert normalized["genelists"] == []
    assert normalized["cnveffects"] == []
    assert normalized is not payload
