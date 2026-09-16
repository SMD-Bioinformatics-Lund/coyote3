"""Role matching must not depend on tumour/normal column ordering."""

import pytest

from api.application.ingest import parsers  # noqa: F401 -- initialize the public parser entrypoint
from api.application.ingest.analysis_parsers import resolve_vcf_roles


def test_matches_reversed_columns():
    roles, warnings = resolve_vcf_roles(["normal", "tumour"], "tumour", "normal")
    assert roles == {"tumour": "case", "normal": "control"}
    assert warnings == []


def test_neither_matches_warns_and_uses_column_order():
    roles, warnings = resolve_vcf_roles(["first", "second"], "missing-case", "missing-control")
    assert roles == {"first": "case", "second": "control"}
    assert "Using first column as case" in warnings[0]


@pytest.mark.parametrize("case,control", [("missing", "normal"), ("tumour", "missing")])
def test_partial_match_preserves_correct_role(case, control):
    roles, warnings = resolve_vcf_roles(["normal", "tumour"], case, control)
    assert roles == {"normal": "control", "tumour": "case"}
    assert warnings


def test_unpaired_case():
    assert resolve_vcf_roles(["tumour"], "tumour", None) == ({"tumour": "case"}, [])


def test_multisample_requires_explicit_matches():
    with pytest.raises(ValueError, match="unambiguously"):
        resolve_vcf_roles(["a", "b", "c"], "a", "missing")
    assert resolve_vcf_roles(["a", "b", "c"], "b", "c")[0] == {"b": "case", "c": "control"}


def test_identical_ids_rejected():
    with pytest.raises(ValueError, match="must differ"):
        resolve_vcf_roles(["a", "b"], "a", "a")
