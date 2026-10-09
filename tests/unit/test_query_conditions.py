"""Exercise condition validation, query compilation, evaluation and clinical scope boundaries."""

from typing import get_args, get_origin

import mongomock
import pytest
from pydantic import BaseModel, ValidationError

from api.config.clinical_query_policy import resolved_query_policy
from api.contracts.schemas.dna import CnvsDoc, TranslocationsDoc, VariantsDoc
from api.contracts.schemas.query_rules import QueryConditionTest, QueryRuleDraft
from api.contracts.schemas.rna import FusionsDoc
from api.domain.core.dna.cnvqueries import build_cnv_query
from api.domain.core.dna.translocqueries import build_transloc_query, filter_translocations_by_genes
from api.domain.core.dna.varqueries import build_query
from api.domain.core.rna.fusion_query_builder import build_fusion_query
from api.domain.query_conditions import FIELD_CATALOG, compile_condition, matches_condition


def predicate(field, operator, value):
    return {"type": "predicate", "field": field, "operator": operator, "value": value}


@pytest.mark.parametrize("analysis", ["snv", "cnv", "fusion", "translocation"])
def test_query_builders_resolve_gene_references_and_keep_sample_scope(analysis):
    fields = {
        "snv": "genes",
        "cnv": "genes.gene",
        "fusion": "gene1",
        "translocation": "INFO.ANN.Gene_Name",
    }
    key = {"snv": "snvlists", "cnv": "cnvlists"}.get(analysis, "fusionlists")
    node = predicate(fields[analysis], "in", {"source": "sample.filters", "key": key})
    policy = resolved_query_policy(
        analysis,
        "exception_only",
        [{"id": "exclude", "mode": "exclude", "condition": node}],
    )
    settings = {"id": "one", "filter_genes": ["TP53"]}
    if analysis == "snv":
        query = build_query("example", settings, policy=policy)
    elif analysis == "cnv":
        settings.update(
            cnv_loss_cutoff=0.8, cnv_gain_cutoff=1.2, min_cnv_size=0, max_cnv_size=1000000
        )
        query = build_cnv_query("one", settings, policy=policy)
    elif analysis == "fusion":
        query = build_fusion_query("example", settings, policy=policy)
    else:
        query = build_transloc_query("one", settings, policy=policy)
    assert query["SAMPLE_ID"] == "one"
    assert "sample.filters" not in str(query)
    assert "TP53" in str(query)


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


@pytest.mark.parametrize(
    "analysis,field,key,settings_key",
    [
        ("snv", "genes", "snvlists", "filter_genes"),
        ("cnv", "genes.gene", "cnvlists", "filter_genes"),
        ("translocation", "INFO.ANN.Gene_Name", "fusionlists", "filter_genes"),
        ("fusion", "calls.caller", "fusion_callers", "fusion_callers"),
    ],
)
def test_filter_references_resolve_per_sample_without_mutating_tree(
    analysis, field, key, settings_key
):
    node = predicate(field, "in", {"source": "sample.filters", "key": key})
    compile_condition(node, analysis, allow_references=True)
    assert compile_condition(node, analysis, filter_values={settings_key: ["A"]}) == {
        field: {"$in": ["A"]}
    }
    assert compile_condition(node, analysis, filter_values={settings_key: ["B"]}) == {
        field: {"$in": ["B"]}
    }
    assert node["value"] == {"source": "sample.filters", "key": key}
    with pytest.raises(ValueError, match="context"):
        compile_condition(node, analysis)


def test_referenced_genes_can_exceed_manual_entry_limit_and_preserve_empty_semantics():
    node = predicate("genes", "in", {"source": "sample.filters", "key": "snvlists"})
    genes = [f"GENE{i}" for i in range(500)]
    assert (
        compile_condition(node, "snv", filter_values={"filter_genes": genes})["genes"]["$in"]
        == genes
    )
    assert not matches_condition(
        node, "snv", {"genes": ["BRAF"]}, filter_values={"filter_genes": []}
    )
    node["operator"] = "nin"
    assert matches_condition(node, "snv", {"genes": ["BRAF"]}, filter_values={"filter_genes": []})
    node["operator"] = "all"
    assert not matches_condition(node, "snv", {"genes": []}, filter_values={"filter_genes": []})


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
    "field,operator,reference",
    [
        ("genes", "in", {"source": "sample.filters", "key": "cnvlists"}),
        ("genes", "eq", {"source": "sample.filters", "key": "snvlists"}),
        ("ALT", "in", {"source": "sample.filters", "key": "snvlists"}),
        ("genes", "in", {"source": "sample.filters", "key": "snvlists", "values": ["BRAF"]}),
    ],
)
def test_invalid_or_copied_reference_payloads_are_rejected(field, operator, reference):
    with pytest.raises(ValueError):
        compile_condition(predicate(field, operator, reference), "snv", allow_references=True)


def test_resolved_reference_does_not_accept_raw_mongo_values():
    node = predicate("genes", "in", {"source": "sample.filters", "key": "snvlists"})
    with pytest.raises(ValueError):
        compile_condition(node, "snv", filter_values={"filter_genes": {"$ne": None}})


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
    "operator,value",
    [
        ("eq", 10),
        ("ne", 12),
        ("gt", 5),
        ("gte", 10),
        ("lt", 11),
        ("lte", 10),
        ("in", [10, 12]),
        ("nin", [9]),
        ("exists", True),
        ("type", "int"),
        ("mod", [3, 1]),
        ("bitsAllSet", [1, 3]),
        ("bitsAnySet", [0, 1]),
        ("bitsAllClear", [0, 2]),
        ("bitsAnyClear", [0, 1]),
    ],
)
def test_numeric_operators_compile_and_evaluate(operator, value):
    node = predicate("size", operator, value)
    assert compile_condition(node, "cnv") == {"size": {f"${operator}": value}}
    assert matches_condition(node, "cnv", {"size": 10})


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
    "node,documents",
    [
        (predicate("ratio", "eq", None), [{}, {"ratio": None}, {"ratio": 0}, {"ratio": "0"}]),
        (predicate("ratio", "ne", None), [{}, {"ratio": None}, {"ratio": 0}]),
        (predicate("ratio", "gt", 0), [{"ratio": "2"}, {"ratio": True}, {"ratio": 2.0}, {}]),
        (
            predicate("callers", "all", ["a", "b"]),
            [{"callers": ["a", "b"]}, {"callers": ["b"]}, {}],
        ),
        (predicate("callers", "size", 0), [{"callers": []}, {"callers": ["a"]}, {}]),
        (predicate("type", "regex", "^GA(IN|INED)$"), [{"type": "GAIN"}, {"type": "loss"}, {}]),
        ({"type": "not", "child": predicate("size", "gte", 10)}, [{"size": 2}, {"size": 12}, {}]),
        (
            {
                "type": "nor",
                "children": [predicate("size", "gte", 10), predicate("type", "eq", "LOSS")],
            },
            [{"size": 2}, {"size": 12}, {"type": "LOSS"}, {}],
        ),
    ],
)
def test_evaluator_agrees_with_mongo_matching(node, documents):
    collection = mongomock.MongoClient().synthetic.findings
    collection.insert_many([{"_id": index, **doc} for index, doc in enumerate(documents)])
    matched = {doc["_id"] for doc in collection.find(compile_condition(node, "cnv"))}
    assert [matches_condition(node, "cnv", doc) for doc in documents] == [
        index in matched for index in range(len(documents))
    ]


def test_element_match_does_not_combine_different_callers():
    node = {
        "type": "elem_match",
        "field": "calls",
        "condition": {
            "type": "all",
            "children": [
                predicate("calls.caller", "eq", "arriba"),
                predicate("calls.spanreads", "gte", 5),
                {
                    "type": "any",
                    "children": [
                        predicate("calls.effect", "eq", "in-frame"),
                        predicate("calls.selected", "eq", 1),
                    ],
                },
            ],
        },
    }
    documents = [
        {"calls": [{"caller": "arriba", "spanreads": 8, "effect": "in-frame"}]},
        {
            "calls": [
                {"caller": "arriba", "spanreads": 1, "effect": "in-frame"},
                {"caller": "starfusion", "spanreads": 9, "selected": 1},
            ]
        },
    ]
    collection = mongomock.MongoClient().synthetic.fusions
    collection.insert_many(documents)
    assert len(list(collection.find(compile_condition(node, "fusion")))) == 1
    assert [matches_condition(node, "fusion", doc) for doc in documents] == [True, False]


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


def test_complexity_is_bounded():
    node = predicate("size", "gte", 1)
    with pytest.raises(ValueError, match="nodes"):
        compile_condition({"type": "all", "children": [node] * 100}, "cnv")
    for _ in range(8):
        node = {"type": "not", "child": node}
    with pytest.raises(ValueError, match="levels"):
        compile_condition(node, "cnv")


@pytest.mark.parametrize(
    "pattern", [r"\w+", "(?i)BRAF", "(a+)+", "(a|aa)*", "a+a+", "[[:alpha:]]", r"(a)\1"]
)
def test_patterns_reject_engine_dependent_or_repeated_groups(pattern):
    with pytest.raises(ValueError):
        compile_condition(predicate("type", "regex", pattern), "cnv")


@pytest.mark.parametrize(
    "analysis,field",
    [("snv", "POS"), ("cnv", "size"), ("fusion", "gene1"), ("translocation", "POS")],
)
def test_nested_exclusions_preserve_sample_boundary(analysis, field):
    value = "TP53" if analysis == "fusion" else 10
    node = {"type": "any", "children": [predicate(field, "eq", value)]}
    policy = resolved_query_policy(
        analysis,
        "exception_only",
        [
            {"id": "exclude", "mode": "exclude", "condition": node},
            {"id": "admit", "mode": "admit", "condition": predicate(field, "exists", True)},
        ],
    )
    if analysis == "snv":
        query = build_query("example", {"id": "one"}, policy=policy)
    elif analysis == "cnv":
        query = build_cnv_query("one", {}, policy=policy)
    elif analysis == "fusion":
        query = build_fusion_query("example", {"id": "one"}, policy=policy)
    else:
        query = build_transloc_query("one", policy=policy)
    assert query["SAMPLE_ID"] == "one"
    collection = mongomock.MongoClient().synthetic.findings
    allowed = "BRAF" if analysis == "fusion" else 20
    collection.insert_many(
        [
            {"SAMPLE_ID": "one", field: value},
            {"SAMPLE_ID": "one", field: allowed},
            {"SAMPLE_ID": "two", field: allowed},
        ]
    )
    assert [doc[field] for doc in collection.find(query)] == [allowed]


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
