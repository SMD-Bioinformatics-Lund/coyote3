"""Tests for workflow filter normalization helpers."""

from __future__ import annotations

from coyote.domain.common import coercion as norm


def test_nonnegative_integer_coercion_handles_overflow():
    """Malformed infinite values use the same default as other invalid inputs."""
    assert norm.coerce_nonnegative_int(float("inf"), default=7) == 7


def test_coerce_nonnegative_int_handles_valid_invalid_and_negative_values():
    assert norm.coerce_nonnegative_int("5") == 5
    assert norm.coerce_nonnegative_int(3) == 3
    assert norm.coerce_nonnegative_int("-1", default=7) == 7
    assert norm.coerce_nonnegative_int(None, default=9) == 9
    assert norm.coerce_nonnegative_int("bad", default=11) == 11
