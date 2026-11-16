"""Exercise condition validation, query compilation, evaluation and clinical scope boundaries."""

from typing import get_args, get_origin

import pytest
from coyote.config.clinical_query_policy import resolved_query_policy
from coyote.contracts.schemas.dna import CnvsDoc, TranslocationsDoc, VariantsDoc
from coyote.contracts.schemas.query_rules import QueryConditionTest, QueryRuleDraft
from coyote.contracts.schemas.rna import FusionsDoc
from coyote.domain.dna.translocqueries import filter_translocations_by_genes
from coyote.domain.query_conditions import FIELD_CATALOG, matches_condition
from pydantic import BaseModel, ValidationError


def predicate(field, operator, value):
    return {"type": "predicate", "field": field, "operator": operator, "value": value}


def test_translocation_report_resolves_gene_reference_from_effective_scope():
    node = predicate(
        "INFO.ANN.Gene_Name",
        "in",
        {
            "source": "sample.filters",
            "key": "fusionlists",
        },
    )
    policy = resolved_query_policy(
        "translocation", None, [{"id": "exclude", "mode": "exclude", "condition": node}]
    )
    documents = [
        {"INFO": {"ANN": [{"Gene_Name": "TP53"}]}},
        {"INFO": {"ANN": [{"Gene_Name": "BRAF"}]}},
    ]
    assert (
        filter_translocations_by_genes(
            documents, filter_genes=["TP53"], restricted=False, policy=policy
        )
        == documents[1:]
    )


def test_nested_numeric_reference_uses_current_depth_threshold():
    node = {
        "type": "elem_match",
        "field": "GT",
        "condition": predicate("GT.DP", "gte", {"source": "sample.filters", "key": "min_depth"}),
    }
    assert matches_condition(node, "snv", {"GT": [{"DP": 50}]}, filter_values={"min_depth": 20})
    assert not matches_condition(
        node, "snv", {"GT": [{"DP": 50}]}, filter_values={"min_depth": 100}
    )


@pytest.mark.parametrize(
    "analysis,model",
    [
        ("snv", VariantsDoc),
        ("cnv", CnvsDoc),
        ("translocation", TranslocationsDoc),
        ("fusion", FusionsDoc),
    ],
)
def test_catalog_paths_are_real_contract_fields(analysis, model):
    def unwrap(annotation):
        if get_origin(annotation):
            return unwrap(next(arg for arg in get_args(annotation) if arg is not type(None)))
        return annotation

    for path in FIELD_CATALOG[analysis]:
        if analysis == "snv" and path in {"INFO.SVTYPE", "INFO.MYELOID_GERMLINE"}:
            assert unwrap(model.model_fields["INFO"].annotation).model_config["extra"] == "allow"
            continue
        current = model
        for segment in path.split("."):
            assert issubclass(current, BaseModel), path
            fields = {
                field.serialization_alias or name: field
                for name, field in current.model_fields.items()
            }
            assert segment in fields, path
            current = unwrap(fields[segment].annotation)


@pytest.mark.parametrize(
    "actual,divisor,remainder,matched",
    [
        (2**63 - 1, 3, 1, True),
        (-10, 3, -1, True),
        (10, -3, 1, True),
        (float("inf"), 3, 0, False),
        (float("nan"), 3, 0, False),
    ],
)
def test_mod_preserves_integer_precision_and_handles_nonfinite_data(
    actual, divisor, remainder, matched
):
    node = predicate("size", "mod", [divisor, remainder])
    assert matches_condition(node, "cnv", {"size": actual}) is matched


@pytest.mark.parametrize(
    "node",
    [
        predicate("SAMPLE_ID", "eq", "another-sample"),
        predicate("$where", "eq", "true"),
        predicate("size", "$expr", {}),
        predicate("size", "eq", {"$gt": 0}),
        predicate("size", "gt", "10"),
        predicate("size", "eq", True),
        predicate("size", "eq", 1.5),
        predicate("size", "eq", 10**1000),
        predicate("ratio", "eq", float("nan")),
        predicate("type", "gt", "A"),
        predicate("type", "regex", "["),
        predicate("size", "exists", 1),
        predicate("callers", "size", -1),
        predicate("callers", "in", []),
        predicate("size", "mod", [0, 1]),
        predicate("size", "bitsAllSet", [-1]),
        {"type": "all", "children": []},
        {"type": "any", "children": [], "$where": "true"},
        {"type": "not", "child": predicate("size", "eq", 1), "extra": True},
        {"type": "elem_match", "field": "genes", "condition": predicate("ratio", "gte", 2)},
        {"type": []},
    ],
)
def test_invalid_conditions_fail_before_persistence(node):
    with pytest.raises((ValueError, ValidationError)):
        QueryRuleDraft(
            scope={"analysis": "cnv"},
            name="Synthetic",
            reason="Validation",
            content={"exceptions": [{"id": "example", "mode": "exclude", "condition": node}]},
        )


def test_translocation_report_filter_obeys_nested_exclusions():
    node = {
        "type": "all",
        "children": [predicate("POS", "gte", 10), predicate("INFO.SOMATIC", "eq", True)],
    }
    policy = resolved_query_policy(
        "translocation", None, [{"id": "exclude", "mode": "exclude", "condition": node}]
    )
    documents = [
        {"POS": 15, "INFO": {"SOMATIC": True}},
        {"POS": 15, "INFO": {"SOMATIC": False}},
        {"POS": 5},
    ]
    result = filter_translocations_by_genes(
        documents, filter_genes=[], restricted=False, policy=policy
    )
    assert result == documents[1:]


def test_synthetic_example_limit_and_schema():
    request = QueryConditionTest(
        analysis="snv", condition=predicate("POS", "gte", 1), documents=[{"POS": 4}]
    )
    assert request.condition.field == "POS"
    with pytest.raises(ValidationError):
        QueryConditionTest(
            analysis="snv", condition=predicate("POS", "gte", 1), documents=[{}] * 51
        )
