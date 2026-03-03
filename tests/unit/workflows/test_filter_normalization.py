"""Tests for workflow filter normalization helpers."""

from __future__ import annotations

from api.core.workflows import filter_normalization as norm


def test_coerce_nonnegative_int_handles_valid_invalid_and_negative_values():
    assert norm.coerce_nonnegative_int("5") == 5
    assert norm.coerce_nonnegative_int(3) == 3
    assert norm.coerce_nonnegative_int("-1", default=7) == 7
    assert norm.coerce_nonnegative_int(None, default=9) == 9
    assert norm.coerce_nonnegative_int("bad", default=11) == 11


def test_normalize_rna_filter_keys_uses_canonical_fields_and_preserves_other_keys():
    payload = {"spanning_reads": "4", "spanning_pairs": "2", "label": "rna"}

    normalized = norm.normalize_rna_filter_keys(payload)

    assert normalized["min_spanning_reads"] == 4
    assert normalized["min_spanning_pairs"] == 2
    assert normalized["label"] == "rna"
    assert payload.get("min_spanning_reads") is None


def test_normalize_rna_filter_keys_prefers_min_keys_when_present():
    payload = {"min_spanning_reads": "8", "spanning_reads": "2", "min_spanning_pairs": 3}

    normalized = norm.normalize_rna_filter_keys(payload)

    assert normalized["min_spanning_reads"] == 8
    assert normalized["min_spanning_pairs"] == 3


def test_normalize_dna_filter_keys_returns_copy():
    payload = {"min_alt_reads": 5}

    normalized = norm.normalize_dna_filter_keys(payload)

    assert normalized == payload
    assert normalized is not payload
