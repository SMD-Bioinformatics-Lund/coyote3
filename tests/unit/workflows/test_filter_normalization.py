"""Tests for workflow filter normalization helpers."""

from __future__ import annotations

from api.domain.core.workflows import filter_normalization as norm


def test_coerce_nonnegative_int_handles_valid_invalid_and_negative_values():
    """Test coerce nonnegative int handles valid invalid and negative values.

    Returns:
        The function result.
    """
    assert norm.coerce_nonnegative_int("5") == 5
    assert norm.coerce_nonnegative_int(3) == 3
    assert norm.coerce_nonnegative_int("-1", default=7) == 7
    assert norm.coerce_nonnegative_int(None, default=9) == 9
    assert norm.coerce_nonnegative_int("bad", default=11) == 11


def test_normalize_rna_filter_keys_uses_canonical_fields_and_preserves_other_keys():
    """Test normalize rna filter keys uses canonical fields and preserves other keys.

    Returns:
        The function result.
    """
    payload = {"min_spanning_reads": "4", "min_spanning_pairs": "2", "label": "rna"}

    normalized = norm.normalize_rna_filter_keys(payload)

    assert normalized["min_spanning_reads"] == 4
    assert normalized["min_spanning_pairs"] == 2
    assert normalized["label"] == "rna"
    assert payload["min_spanning_reads"] == "4"
    assert normalized is not payload


def test_normalize_rna_filter_keys_ignores_retired_threshold_aliases():
    """Test normalize rna filter keys ignores retired threshold aliases.

    Returns:
        The function result.
    """
    payload = {"spanning_reads": "2", "spanning_pairs": 3}

    normalized = norm.normalize_rna_filter_keys(payload)

    assert normalized["min_spanning_reads"] == 0
    assert normalized["min_spanning_pairs"] == 0


def test_normalize_dna_filter_keys_returns_copy():
    """Test normalize dna filter keys returns copy.

    Returns:
        The function result.
    """
    payload = {"min_alt_reads": 5}

    normalized = norm.normalize_dna_filter_keys(payload)

    assert normalized["min_alt_reads"] == 5
    assert normalized["vep_consequences"] == []
    assert normalized["snvlists"] == []
    assert normalized["cnveffects"] == []
    assert normalized is not payload
