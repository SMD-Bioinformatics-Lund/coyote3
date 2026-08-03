"""Unit tests for ASPC-driven CNV/fusion/translocation query strategy."""

from api.domain.core.dna.cnvqueries import build_cnv_query, include_normal_cnvs
from api.domain.core.dna.dna_filters import cnvtype_variant
from api.domain.core.dna.varqueries import build_pos_genes_filter
from api.domain.core.rna.fusion_query_builder import build_fusion_query


def test_build_cnv_query_applies_base_guards() -> None:
    query = build_cnv_query(
        "SAMPLE_1",
        {
            "cnv_loss_cutoff": -0.3,
            "cnv_gain_cutoff": 0.3,
            "min_cnv_size": 100,
            "max_cnv_size": 10000,
            "filter_genes": ["TP53"],
        },
    )
    assert query["SAMPLE_ID"] == "SAMPLE_1"
    assert "$and" in query
    gene_clause = next(
        clause
        for clause in query["$and"]
        if isinstance(clause, dict)
        and "$or" in clause
        and any(isinstance(option, dict) and "genes.gene" in option for option in clause["$or"])
    )
    assert {"genes.gene": {"$in": ["TP53"]}} in gene_clause["$or"]


def test_build_cnv_query_filters_against_stored_gene_array_shape() -> None:
    query = build_cnv_query(
        "SAMPLE_1",
        {
            "cnv_loss_cutoff": -0.3,
            "cnv_gain_cutoff": 0.3,
            "min_cnv_size": 100,
            "max_cnv_size": 10000,
            "filter_genes": ["EGFR", "ERBB2"],
        },
    )

    gene_clauses = [
        clause
        for clause in query["$and"]
        if any(
            isinstance(option, dict) and "genes.gene" in option for option in clause.get("$or", [])
        )
    ]
    assert len(gene_clauses) == 1
    assert gene_clauses[0]["$or"] == [
        {"genes.gene": {"$in": ["EGFR", "ERBB2"]}},
        {"panel_gene": {"$in": ["EGFR", "ERBB2"]}},
    ]


def test_build_cnv_query_has_no_gene_clause_for_unrestricted_scope() -> None:
    """An ASP without covered genes leaves WGS/WTS CNVs unrestricted by gene."""
    query = build_cnv_query(
        "SAMPLE_1",
        {
            "cnv_loss_cutoff": -0.3,
            "cnv_gain_cutoff": 0.3,
            "min_cnv_size": 100,
            "max_cnv_size": 10000,
            "filter_genes": [],
        },
    )

    assert all("genes.gene" not in str(clause) for clause in query["$and"])
    assert all("panel_gene" not in str(clause) for clause in query["$and"])


def test_build_cnv_query_rejects_all_rows_for_empty_selected_scope() -> None:
    query = build_cnv_query(
        "SAMPLE_1",
        {
            "cnv_loss_cutoff": -0.3,
            "cnv_gain_cutoff": 0.3,
            "min_cnv_size": 100,
            "max_cnv_size": 10000,
            "filter_genes": [],
            "restrict_to_genes": True,
        },
    )

    assert {"_id": {"$exists": False}} in query["$and"]


def test_build_snv_gene_filter_rejects_all_rows_for_empty_selected_scope() -> None:
    assert build_pos_genes_filter({"filter_genes": [], "restrict_to_genes": True}) == {
        "$and": [{"_id": {"$exists": False}}]
    }


def test_build_cnv_query_accepts_ratio_less_structural_read_calls() -> None:
    query = build_cnv_query(
        "SAMPLE_1",
        {
            "cnv_loss_cutoff": -0.3,
            "cnv_gain_cutoff": 0.3,
            "min_cnv_size": 100,
            "max_cnv_size": 10000,
        },
    )

    evidence_clause = next(
        clause
        for clause in query["$and"]
        if any(
            isinstance(option, dict)
            and any(
                isinstance(child, dict)
                and "$or" in child
                and {"SR": {"$exists": True, "$nin": [None, "", []]}} in child["$or"]
                for child in option.get("$and", [])
            )
            for option in clause.get("$or", [])
        )
    )
    assert evidence_clause


def test_build_cnv_query_preserves_historical_strict_boundaries_and_amplification() -> None:
    """Ratio CNVs use strict cutoffs while high amplifications bypass the size ceiling."""
    query = build_cnv_query(
        "SAMPLE_1",
        {
            "cnv_loss_cutoff": -0.3,
            "cnv_gain_cutoff": 0.3,
            "min_cnv_size": 100,
            "max_cnv_size": 10000,
        },
    )

    query_text = str(query)
    assert "'$lt': -0.3" in query_text
    assert "'$gt': 0.3" in query_text
    assert "'$gt': 100" in query_text
    assert "'$lt': 10000" in query_text
    assert "'$gt': 3" in query_text


def test_build_cnv_query_keeps_normal_calls_for_wgs() -> None:
    filters = {
        "cnv_loss_cutoff": -0.3,
        "cnv_gain_cutoff": 0.3,
        "min_cnv_size": 100,
        "max_cnv_size": 10000,
    }
    query = build_cnv_query("SAMPLE_1", filters, include_normal=True)

    assert all("NORMAL" not in str(clause) for clause in query["$and"])
    assert include_normal_cnvs({"sequencing_scope": "wgs"}) is True
    assert include_normal_cnvs({}, {"asp_group": "tumwgs"}) is True
    assert include_normal_cnvs({"sequencing_scope": "panel"}, {"asp_group": "solid"}) is False


def test_cnv_effect_filter_retains_untyped_structural_read_calls() -> None:
    cnvs = [
        {"_id": "ratio-gain", "ratio": 0.8},
        {"_id": "declared-loss", "type": "DEL"},
        {"_id": "manta-breakpoint", "ratio": None, "SR": "43,0"},
        {"_id": "unsupported", "ratio": None},
    ]

    assert [row["_id"] for row in cnvtype_variant(cnvs, ["AMP"])] == [
        "ratio-gain",
        "manta-breakpoint",
    ]


def test_build_fusion_query_applies_base_filters() -> None:
    query = build_fusion_query(
        "fusion",
        {
            "id": "SAMPLE_1",
            "min_spanning_reads": 10,
            "min_spanning_pairs": 10,
            "fusion_effects": ["in-frame"],
            "fusion_callers": ["arriba"],
            "checked_fusionlists": ["FCknown"],
            "filter_genes": ["KMT2A"],
        },
    )
    assert "calls" in query
    assert "$or" in query


def test_build_fusion_query_applies_thresholds_without_selected_callers() -> None:
    """Thresholds apply directly to every call when callers are not restricted."""
    query = build_fusion_query(
        "wts",
        {
            "id": "SAMPLE_1",
            "min_spanning_reads": "7",
            "min_spanning_pairs": "3",
            "fusion_effects": [],
            "fusion_callers": [],
            "checked_fusionlists": [],
            "filter_genes": [],
        },
    )

    assert query == {
        "SAMPLE_ID": "SAMPLE_1",
        "calls": {"$elemMatch": {"spanreads": {"$gte": 7}, "spanpairs": {"$gte": 3}}},
    }


def test_build_fusion_query_applies_known_list_and_arriba_pair_rule() -> None:
    """Arriba has no spanning-pair predicate; other callers retain it."""
    query = build_fusion_query(
        "fusionrna",
        {
            "id": "SAMPLE_1",
            "min_spanning_reads": 5,
            "min_spanning_pairs": 2,
            "fusion_effects": ["in-frame"],
            "fusion_callers": ["arriba", "starfusion"],
            "checked_fusionlists": ["FCknown", "mitelman"],
            "filter_genes": ["KMT2A"],
        },
    )

    call_match = query["calls"]["$elemMatch"]
    assert call_match["effect"] == {"$in": ["in-frame"]}
    assert call_match["desc"] == {"$regex": "known|mitelman", "$options": "i"}
    assert call_match["$or"] == [
        {"caller": "arriba", "spanreads": {"$gte": 5}},
        {
            "caller": "starfusion",
            "spanreads": {"$gte": 5},
            "spanpairs": {"$gte": 2},
        },
    ]
    assert query["$or"] == [{"gene1": {"$in": ["KMT2A"]}}, {"gene2": {"$in": ["KMT2A"]}}]


def test_build_fusion_query_keeps_unconfigured_groups_sample_scoped() -> None:
    """An unsupported group never inherits fusion thresholds accidentally."""
    assert build_fusion_query("solid", {"id": "SAMPLE_1"}) == {"SAMPLE_ID": "SAMPLE_1"}


def test_build_fusion_query_rejects_all_rows_for_empty_selected_scope() -> None:
    query = build_fusion_query(
        "wts",
        {
            "id": "SAMPLE_1",
            "filter_genes": [],
            "restrict_to_genes": True,
        },
    )

    assert query["_id"] == {"$exists": False}
