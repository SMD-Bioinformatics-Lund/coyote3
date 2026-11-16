"""Exercise condition validation, query compilation, evaluation and clinical scope boundaries."""

import mongomock
import pytest
from coyote.config.clinical_query_policy import resolved_query_policy
from coyote.domain.dna.cnvqueries import build_cnv_query
from coyote.domain.dna.translocqueries import build_transloc_query
from coyote.domain.dna.varqueries import build_query
from coyote.domain.query_conditions import compile_condition, matches_condition
from coyote.domain.rna.fusion_query_builder import build_fusion_query
from coyote_mongo.selection import compile_selection


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
        query = compile_selection(build_query("example", settings, policy=policy))
    elif analysis == "cnv":
        settings.update(
            cnv_loss_cutoff=0.8, cnv_gain_cutoff=1.2, min_cnv_size=0, max_cnv_size=1000000
        )
        query = compile_selection(build_cnv_query("one", settings, policy=policy))
    elif analysis == "fusion":
        query = compile_selection(build_fusion_query("example", settings, policy=policy))
    else:
        query = compile_selection(build_transloc_query("one", settings, policy=policy))
    assert query["SAMPLE_ID"] == "one"
    assert "sample.filters" not in str(query)
    assert "TP53" in str(query)


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
    compile_selection(compile_condition(node, analysis, allow_references=True))
    assert compile_selection(
        compile_condition(node, analysis, filter_values={settings_key: ["A"]})
    ) == {field: {"$in": ["A"]}}
    assert compile_selection(
        compile_condition(node, analysis, filter_values={settings_key: ["B"]})
    ) == {field: {"$in": ["B"]}}
    assert node["value"] == {"source": "sample.filters", "key": key}
    with pytest.raises(ValueError, match="context"):
        compile_selection(compile_condition(node, analysis))


def test_referenced_genes_can_exceed_manual_entry_limit_and_preserve_empty_semantics():
    node = predicate("genes", "in", {"source": "sample.filters", "key": "snvlists"})
    genes = [f"GENE{i}" for i in range(500)]
    assert (
        compile_selection(compile_condition(node, "snv", filter_values={"filter_genes": genes}))[
            "genes"
        ]["$in"]
        == genes
    )
    assert not matches_condition(
        node, "snv", {"genes": ["BRAF"]}, filter_values={"filter_genes": []}
    )
    node["operator"] = "nin"
    assert matches_condition(node, "snv", {"genes": ["BRAF"]}, filter_values={"filter_genes": []})
    node["operator"] = "all"
    assert not matches_condition(node, "snv", {"genes": []}, filter_values={"filter_genes": []})


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
        compile_selection(
            compile_condition(predicate(field, operator, reference), "snv", allow_references=True)
        )


def test_resolved_reference_does_not_accept_raw_mongo_values():
    node = predicate("genes", "in", {"source": "sample.filters", "key": "snvlists"})
    with pytest.raises(ValueError):
        compile_selection(
            compile_condition(node, "snv", filter_values={"filter_genes": {"$ne": None}})
        )


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
    assert compile_selection(compile_condition(node, "cnv")) == {"size": {f"${operator}": value}}
    assert matches_condition(node, "cnv", {"size": 10})


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
    matched = {
        doc["_id"] for doc in collection.find(compile_selection(compile_condition(node, "cnv")))
    }
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
    assert len(list(collection.find(compile_selection(compile_condition(node, "fusion"))))) == 1
    assert [matches_condition(node, "fusion", doc) for doc in documents] == [True, False]


def test_complexity_is_bounded():
    node = predicate("size", "gte", 1)
    with pytest.raises(ValueError, match="nodes"):
        compile_selection(compile_condition({"type": "all", "children": [node] * 100}, "cnv"))
    for _ in range(8):
        node = {"type": "not", "child": node}
    with pytest.raises(ValueError, match="levels"):
        compile_selection(compile_condition(node, "cnv"))


@pytest.mark.parametrize(
    "pattern", [r"\w+", "(?i)BRAF", "(a+)+", "(a|aa)*", "a+a+", "[[:alpha:]]", r"(a)\1"]
)
def test_patterns_reject_engine_dependent_or_repeated_groups(pattern):
    with pytest.raises(ValueError):
        compile_selection(compile_condition(predicate("type", "regex", pattern), "cnv"))


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
        query = compile_selection(build_query("example", {"id": "one"}, policy=policy))
    elif analysis == "cnv":
        query = compile_selection(build_cnv_query("one", {}, policy=policy))
    elif analysis == "fusion":
        query = compile_selection(build_fusion_query("example", {"id": "one"}, policy=policy))
    else:
        query = compile_selection(build_transloc_query("one", policy=policy))
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
