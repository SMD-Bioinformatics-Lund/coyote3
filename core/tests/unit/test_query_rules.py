"""Synthetic tests for hierarchical query-policy governance and query isolation."""

import pytest
from coyote.application.query_rules.service import QueryRuleService
from coyote.contracts.schemas.query_rules import (
    QueryRuleContent,
    QueryRuleDraft,
    QueryRulePreview,
    QueryRuleScope,
)
from coyote.domain.query_conditions import condition_catalog
from pydantic import ValidationError


def test_condition_choices_expose_references_without_loading_or_copying_values():
    choices = QueryRuleService(None).condition_options()
    assert "gene_lists" not in choices
    snv = {field["path"]: field for field in choices["fields"]["snv"]}
    assert snv["INFO.selected_CSQ.SYMBOL"]["value_role"] == "gene"
    assert snv["INFO.selected_CSQ.SYMBOL"]["filter_references"][0]["key"] == "snvlists"
    assert snv["GT.DP"]["filter_references"][0]["key"] == "min_depth"
    assert snv["INFO.selected_CSQ.CADD_PHRED"]["kind"] == "string"
    assert "SAMPLE_ID" not in snv
    assert all("suggestions" not in field for field in condition_catalog()["fields"]["snv"])
    fusion = {field["path"]: field for field in choices["fields"]["fusion"]}
    assert "value_role" not in fusion["genes"]
    assert fusion["gene1"]["value_role"] == "gene"


def scope(**values):
    """Create a synthetic clinical scope with explicit overrides."""
    return QueryRuleScope(assay_group="example", analysis="snv", **values)


def draft(selected=None, **content):
    """Build a valid editable version with a documented synthetic purpose."""
    return QueryRuleDraft(
        scope=selected or scope(),
        name="Example",
        reason="Validation",
        content=QueryRuleContent(**content),
    )


@pytest.mark.parametrize(
    "exception",
    [
        {"id": "unsafe", "mode": "admit", "$where": "true"},
        {"id": "unsafe", "mode": "admit", "info_equals": {"DP": {"$gt": 0}}},
        {"id": "unsafe", "mode": "admit", "info_equals": []},
        {"id": "unsafe", "mode": "admit", "asp_ids": ["other"], "genes": ["TP53"]},
        {"id": "empty", "mode": "admit"},
        {"id": "fraction", "mode": "admit", "position_min": 1.5},
        {"id": "negative", "mode": "admit", "position_min": -1},
        {"id": "object", "mode": "admit", "genes": [{"$ne": "TP53"}]},
    ],
)
def test_unsafe_or_unbounded_criteria_rejected(exception):
    with pytest.raises(ValidationError):
        draft(exceptions=[exception])


def test_invalid_preview_is_request_validation_error():
    with pytest.raises(ValidationError):
        QueryRulePreview(scope=scope(), content={"exceptions": [{"id": "x", "mode": "invalid"}]})


@pytest.mark.parametrize(
    "values",
    [
        {"family": "panel-dna"},
        {"family": "panel-dna", "modality": "rna"},
        {"environment": "unknown"},
    ],
)
def test_query_scope_rejects_invalid_dimensions(values):
    with pytest.raises(ValidationError):
        scope(**values)


def test_generated_identity_normalizes_base_and_separates_analysis():
    assert scope().key() == "example__all__base__somatic_snvs"
    assert scope(asp_id="panel", diagnosis_id="base").key() == "example__panel__base__somatic_snvs"
    assert (
        scope(asp_id="panel", diagnosis_id="myeloid").key()
        == "example__panel__myeloid__somatic_snvs"
    )
    assert (
        QueryRuleScope(analysis="cnv", assay_group="example").key()
        == "example__all__base__somatic_cnvs"
    )
    assert (
        QueryRuleScope(analysis="snv", intent="germline").key()
        == "default__all__base__germline_snvs"
    )
