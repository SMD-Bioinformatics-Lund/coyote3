"""Adapters own executable queries and provider IDs; core selections are plain values."""

from copy import deepcopy
from types import SimpleNamespace

import mongomock
import pytest
from bson import ObjectId
from coyote.domain.selection import Operator, RecordField, select, selection_data
from coyote_mongo.records import application_record
from coyote_mongo.repositories.variants import VariantsRepository
from coyote_mongo.selection import compile_selection
from mongo_test_support.settings import mongo_runtime


def test_selection_is_independent_of_caller_and_compiler_mutations():
    genes = ["TP53"]
    expression = select({"genes": {Operator.IN: genes}})
    genes.append("BRAF")
    assert expression.criteria["genes"][Operator.IN] == ("TP53",)
    with pytest.raises(TypeError):
        expression.criteria["genes"][Operator.IN] = ("BRAF",)
    assert deepcopy(expression) is expression
    compiled = compile_selection(expression)
    compiled["genes"]["$in"].append("BRAF")
    assert compile_selection(expression) == {"genes": {"$in": ["TP53"]}}


def test_adapter_can_rename_stored_fields_without_changing_clinical_selections():
    expression = select(
        {
            "INFO.selected_CSQ.SYMBOL": "TP53",
            "GT": {Operator.ELEMENT: {"type": "case", "AF": {Operator.AT_LEAST: 0.05}}},
        }
    )
    assert compile_selection(
        expression,
        field_names={
            "INFO.selected_CSQ.SYMBOL": "annotations.primary.gene",
            "GT": "genotypes",
            "GT.AF": "genotypes.allele_fraction",
        },
    ) == {
        "annotations.primary.gene": "TP53",
        "genotypes": {"$elemMatch": {"type": "case", "allele_fraction": {"$gte": 0.05}}},
    }
    assert "INFO.selected_CSQ.SYMBOL" in expression.criteria


def test_field_mapping_does_not_rewrite_literal_objects_or_escape_array_scope():
    expression = select({"annotation": {Operator.EQUAL: {"gene": "TP53"}}})
    assert compile_selection(
        expression, field_names={"annotation": "metadata", "annotation.gene": "metadata.symbol"}
    ) == {"metadata": {"$eq": {"gene": "TP53"}}}
    with pytest.raises(ValueError, match="containing record"):
        compile_selection(
            select({"GT": {Operator.ELEMENT: {"AF": 0.1}}}),
            field_names={"GT.AF": "outside.frequency"},
        )


@pytest.mark.parametrize(
    "criteria",
    [
        {"$where": "untrusted"},
        {"genes": {"$in": ["TP53"]}},
        {"_id": "sample"},
        {"SAMPLE_ID": "sample"},
        {"gene": ObjectId("000000000000000000000001")},
    ],
)
def test_selection_rejects_storage_syntax_and_native_identifiers(criteria):
    with pytest.raises(ValueError):
        select(criteria)


def test_adapter_rejects_an_untyped_query_dictionary():
    with pytest.raises(TypeError):
        compile_selection({"SAMPLE_ID": "sample"})


def test_logical_identities_are_translated_only_by_the_adapter():
    identifier = "000000000000000000000001"
    expression = select({RecordField.IDENTITY: identifier})
    assert selection_data(expression) == {"identity": identifier}
    assert compile_selection(expression) == {"_id": ObjectId(identifier)}
    reference = select({RecordField.ANNOTATION_REFERENCE: {Operator.IN: [identifier]}})
    assert compile_selection(reference) == {
        "annotation_oid": {"$in": [ObjectId(identifier), identifier]}
    }
    assert reference.criteria[RecordField.ANNOTATION_REFERENCE][Operator.IN] == (identifier,)


def test_record_projection_preserves_values_and_stored_documents():
    identifier = ObjectId("000000000000000000000001")
    stored = {"_id": identifier, "comments": [{"_id": identifier}], "value": None, "count": 0}
    assert application_record(stored) == {
        "_id": str(identifier),
        "comments": [{"_id": str(identifier)}],
        "value": None,
        "count": 0,
    }
    assert stored["_id"] is identifier
    assert stored["comments"][0]["_id"] is identifier


def test_finding_reads_return_an_application_iterator_and_string_ids():
    collection = mongomock.MongoClient().synthetic.variants
    identifier = collection.insert_one({"SAMPLE_ID": "sample", "gene": "TP53"}).inserted_id
    repository = VariantsRepository(
        SimpleNamespace(app=mongo_runtime(), variants_collection=collection)
    )
    selected = repository.get_case_variants(select({RecordField.SAMPLE: "sample"}))
    assert not hasattr(selected, "collection")
    assert list(selected) == [{"_id": str(identifier), "SAMPLE_ID": "sample", "gene": "TP53"}]
    assert collection.find_one()["_id"] == identifier
