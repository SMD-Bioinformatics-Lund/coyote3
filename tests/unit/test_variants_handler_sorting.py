"""Unit tests for variant handler cross-sample ordering."""

from __future__ import annotations

from api.infra.mongo.repositories.variants import VariantsRepository


def test_case_af_value_uses_case_gt_and_defaults_to_zero() -> None:
    """Case AF extraction should prefer the case genotype and fall back safely."""
    assert VariantsRepository._case_af_value({"GT": [{"type": "case", "AF": 0.42}]}) == 0.42
    assert VariantsRepository._case_af_value({"GT": [{"type": "control", "AF": 0.9}]}) == 0.0
    assert VariantsRepository._case_af_value({"GT": [{"type": "case", "AF": "bad"}]}) == 0.0
