"""Tests for annotation search query construction."""

from __future__ import annotations

from bson import ObjectId

from api.infra.mongo.repositories.annotations import (
    _annotation_class_value,
    _annotation_object_id,
    _annotation_search_query,
    _classification_text_lookup_query,
)
from api.infra.mongo.repositories.reported_variants import _reported_variant_search_query


def _or_fields(query: dict) -> set[str]:
    if "$and" in query:
        fields: set[str] = set()
        for part in query["$and"]:
            fields.update(_or_fields(part))
        return fields
    return {next(iter(item.keys())) for item in query.get("$or", [])}


def _and_parts(query: dict) -> list[dict]:
    return query.get("$and", [query])


def _first_or_clause(query: dict) -> list[dict]:
    for part in _and_parts(query):
        if "$or" in part:
            return part["$or"]
    return []


def test_annotation_object_ids_use_only_canonical_mongo_object_ids():
    object_id = ObjectId()

    assert _annotation_object_id(object_id) == object_id
    assert _annotation_object_id(str(object_id)) == object_id
    assert _annotation_object_id("historical-string-id") is None


def test_annotation_classes_are_not_coerced_from_historical_strings():
    assert _annotation_class_value(2) == 2
    assert _annotation_class_value("2") is None
    assert _annotation_class_value(True) is None


def test_variant_search_uses_only_canonical_annotation_identity_fields():
    query = _annotation_search_query(
        search_str="p.Arg248Gln",
        search_mode="variant",
        include_annotation_text=False,
        asp_ids=["hema_gmsv1"],
    )

    assert query is not None
    fields = {next(iter(item)) for item in _first_or_clause(query)}
    assert "variant" in fields
    assert "hgvsp" in fields
    assert "hgvsc" in fields
    assert "genomic" in fields
    assert "genomic_hash" in fields
    assert "simple_id" not in fields
    assert fields.isdisjoint(
        {
            "cnv",
            "fusion",
            "translocation",
            "var_p",
            "var_c",
            "var_g",
            "HGVSp",
            "HGVSc",
            "variant_data.HGVSp",
        }
    )
    assert {"$or": [{"text": {"$exists": False}}, {"text": None}, {"text": ""}]} in _and_parts(
        query
    )
    assert {"assay": {"$in": ["hema_gmsv1"]}} in _and_parts(query)


def test_annotation_text_mode_does_not_exclude_text_documents():
    query = _annotation_search_query(
        search_str="FLT3",
        search_mode="annotation",
        include_annotation_text=False,
    )

    assert query == {"text": {"$regex": "FLT3", "$options": "i"}}


def test_all_search_includes_identity_and_context_fields():
    query = _annotation_search_query(
        search_str="DNMT3A",
        search_mode="all",
        include_annotation_text=True,
    )

    assert query is not None
    fields = _or_fields(query)
    assert {
        "gene",
        "transcript",
        "author",
        "subpanel",
        "text",
        "variant",
        "hgvsp",
        "hgvsc",
        "genomic",
        "genomic_hash",
    }.issubset(fields)
    assert "text" not in query


def test_variant_search_uses_entered_regex_pattern_and_ignores_empty_assays():
    query = _annotation_search_query(
        search_str="p\\.",
        search_mode="variant",
        include_annotation_text=False,
        asp_ids=[],
    )

    assert query is not None
    assert _first_or_clause(query)[0]["variant"] == {"$regex": "p\\.", "$options": "i"}
    assert {"assay": {"$in": []}} not in _and_parts(query)


def test_gene_search_uses_only_flat_annotation_gene_fields():
    query = _annotation_search_query(
        search_str="TP53",
        search_mode="gene",
        include_annotation_text=False,
    )

    assert query is not None
    fields = {next(iter(item)) for item in _first_or_clause(query)}
    assert fields == {"gene", "gene1", "gene2"}
    assert {"$or": [{"text": {"$exists": False}}, {"text": None}, {"text": ""}]} in _and_parts(
        query
    )


def test_reported_variant_search_includes_report_snapshot_identity_fields():
    query = _reported_variant_search_query(
        search_str="DNMT3A",
        search_mode="variant",
        asp_ids=["hema_gmsv1"],
    )

    assert query is not None
    fields = _or_fields(query)
    assert {"variant", "hgvsp", "hgvsc", "simple_id"}.issubset(fields)
    assert {
        "$or": [{"assay": {"$in": ["hema_gmsv1"]}}, {"assay_group": {"$in": ["hema_gmsv1"]}}]
    } in _and_parts(query)


def test_reported_variant_gene_search_uses_only_flat_snapshot_fields():
    query = _reported_variant_search_query(
        search_str="TP53",
        search_mode="gene",
        asp_ids=["hema_gmsv1"],
    )

    assert query is not None
    fields = {next(iter(item)) for item in _first_or_clause(query)}
    assert fields == {"gene", "genes", "gene1", "gene2"}
    assert {
        "$or": [{"assay": {"$in": ["hema_gmsv1"]}}, {"assay_group": {"$in": ["hema_gmsv1"]}}]
    } in _and_parts(query)


def test_reported_variant_annotation_text_mode_is_annotation_only():
    assert (
        _reported_variant_search_query(
            search_str="clinical text",
            search_mode="annotation",
        )
        is None
    )


def test_classification_text_lookup_uses_same_variant_identity_and_context():
    query = _classification_text_lookup_query(
        {
            "gene": "TP53",
            "variant": "p.Val157GlyfsTer24",
            "nomenclature": "p",
            "assay": "hematology",
            "subpanel": "base",
            "class": 1,
            "text": None,
        }
    )

    assert query == {
        "gene": "TP53",
        "variant": "p.Val157GlyfsTer24",
        "nomenclature": "p",
        "assay": "hematology",
        "subpanel": "base",
        "text": {"$exists": True, "$type": "string", "$ne": ""},
    }
