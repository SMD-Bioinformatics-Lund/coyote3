"""Tests for annotation search query construction."""

from __future__ import annotations

from api.infra.mongo.repositories.annotations import (
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


def test_variant_search_includes_hgvsp_hgvsc_and_genomic_aliases():
    query = _annotation_search_query(
        search_str="p.Arg248Gln",
        search_mode="variant",
        include_annotation_text=False,
        assays=["hema_GMSv1"],
    )

    assert query is not None
    fields = _or_fields(query)
    assert "variant" in fields
    assert "var_p" in fields
    assert "var_c" in fields
    assert "var_g" in fields
    assert "HGVSp" in fields
    assert "HGVSc" in fields
    assert "variant_data.HGVSp" in fields
    assert {"$or": [{"text": {"$exists": False}}, {"text": None}, {"text": ""}]} in _and_parts(
        query
    )
    assert {"assay": {"$in": ["hema_GMSv1"]}} in _and_parts(query)


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
        "HGVSp",
        "HGVSc",
    }.issubset(fields)
    assert "text" not in query


def test_variant_search_uses_entered_regex_pattern_and_ignores_empty_assays():
    query = _annotation_search_query(
        search_str="p\\.",
        search_mode="variant",
        include_annotation_text=False,
        assays=[],
    )

    assert query is not None
    assert _first_or_clause(query)[0]["variant"] == {"$regex": "p\\.", "$options": "i"}
    assert {"assay": {"$in": []}} not in _and_parts(query)


def test_gene_search_includes_annotation_gene_aliases():
    query = _annotation_search_query(
        search_str="TP53",
        search_mode="gene",
        include_annotation_text=False,
    )

    assert query is not None
    fields = _or_fields(query)
    assert {
        "gene",
        "gene1",
        "gene2",
        "variant_data.gene",
        "variant_data.gene1",
        "variant_data.gene2",
        "variant_data.SYMBOL",
        "variant_data.INFO.selected_CSQ.SYMBOL",
    }.issubset(fields)
    assert {"$or": [{"text": {"$exists": False}}, {"text": None}, {"text": ""}]} in _and_parts(
        query
    )


def test_reported_variant_search_includes_report_snapshot_identity_fields():
    query = _reported_variant_search_query(
        search_str="DNMT3A",
        search_mode="variant",
        assays=["hema_GMSv1"],
    )

    assert query is not None
    fields = _or_fields(query)
    assert {"variant", "hgvsp", "hgvsc", "simple_id"}.issubset(fields)
    assert {
        "$or": [{"assay": {"$in": ["hema_GMSv1"]}}, {"assay_group": {"$in": ["hema_GMSv1"]}}]
    } in _and_parts(query)


def test_reported_variant_gene_search_includes_snapshot_gene_aliases():
    query = _reported_variant_search_query(
        search_str="TP53",
        search_mode="gene",
        assays=["hema_GMSv1"],
    )

    assert query is not None
    fields = _or_fields(query)
    assert {
        "gene",
        "gene1",
        "gene2",
        "variant_data.gene",
        "variant_data.gene1",
        "variant_data.gene2",
        "variant_data.SYMBOL",
        "variant_data.INFO.selected_CSQ.SYMBOL",
    }.issubset(fields)
    assert {
        "$or": [{"assay": {"$in": ["hema_GMSv1"]}}, {"assay_group": {"$in": ["hema_GMSv1"]}}]
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
            "assay": "legacy",
            "subpanel": "legacy",
            "class": 1,
            "text": None,
        }
    )

    assert query == {
        "gene": "TP53",
        "variant": "p.Val157GlyfsTer24",
        "nomenclature": "p",
        "assay": "legacy",
        "subpanel": "legacy",
        "text": {"$exists": True, "$type": "string", "$ne": ""},
    }
