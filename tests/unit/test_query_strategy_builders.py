"""Unit tests for ASPC-driven CNV/fusion/translocation query strategy."""

from api.config.clinical_query_policy import FindingQueryException, FindingQueryPolicy
from api.domain.core.dna.cnvqueries import build_cnv_query, include_normal_cnvs
from api.domain.core.dna.dna_filters import cnvtype_variant
from api.domain.core.dna.translocqueries import (
    build_transloc_query,
    filter_translocations_by_genes,
)
from api.domain.core.dna.varqueries import build_pos_genes_filter
from api.domain.core.rna.fusion_query_builder import build_fusion_query


def _finding_policy(*rules: FindingQueryException) -> FindingQueryPolicy:
    return FindingQueryPolicy(exceptions=rules)


def _finding_rule(
    *, rule_id: str, mode: str, criteria: dict, assay_groups: tuple[str, ...] = ("solid",)
) -> FindingQueryException:
    return FindingQueryException(
        rule_id=rule_id,
        mode=mode,
        intents=("somatic",),
        assay_groups=assay_groups,
        asp_ids=(),
        subpanel_ids=(),
        criteria=criteria,
    )


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


def test_cnv_policy_admission_extends_the_normal_filter_query() -> None:
    policy = _finding_policy(
        _finding_rule(rule_id="retain_egfr", mode="admit", criteria={"genes": ("EGFR",)})
    )
    query = build_cnv_query(
        "SAMPLE_1",
        {
            "assay_group": "solid",
            "cnv_loss_cutoff": -0.3,
            "cnv_gain_cutoff": 0.3,
            "min_cnv_size": 1000,
            "max_cnv_size": 10000,
        },
        policy=policy,
    )

    assert query["$and"][0]["$or"][1] == {
        "$or": [
            {"genes.gene": {"$in": ["EGFR"]}},
            {"panel_gene": {"$in": ["EGFR"]}},
        ]
    }


def test_cnv_policy_is_ignored_outside_its_assay_scope() -> None:
    policy = _finding_policy(
        _finding_rule(rule_id="retain_egfr", mode="admit", criteria={"genes": ("EGFR",)})
    )
    query = build_cnv_query(
        "SAMPLE_1",
        {
            "assay_group": "hematology",
            "cnv_loss_cutoff": -0.3,
            "cnv_gain_cutoff": 0.3,
            "min_cnv_size": 1000,
            "max_cnv_size": 10000,
        },
        policy=policy,
    )

    assert "EGFR" not in str(query)


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


def test_build_fusion_query_applies_gene_scope_and_arriba_pair_rule() -> None:
    """Resolved fusion-list genes scope either partner without filtering evidence text."""
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
    assert call_match["effect"] == {"$regex": "^in-frame$", "$options": "i"}
    assert "desc" not in call_match
    assert call_match["$or"] == [
        {"caller": "arriba", "spanreads": {"$gte": 5}},
        {
            "caller": "starfusion",
            "spanreads": {"$gte": 5},
            "spanpairs": {"$gte": 2},
        },
    ]
    assert query["$or"] == [{"gene1": {"$in": ["KMT2A"]}}, {"gene2": {"$in": ["KMT2A"]}}]


def test_build_fusion_query_keeps_empty_filters_sample_scoped_for_any_rna_group() -> None:
    """An empty filter block remains sample-scoped regardless of RNA assay group."""
    assert build_fusion_query("solid", {"id": "SAMPLE_1"}) == {"SAMPLE_ID": "SAMPLE_1"}


def test_build_fusion_query_applies_filters_to_targeted_rna_panel_groups() -> None:
    """Targeted RNA panels must not bypass the shared fusion filter contract."""
    query = build_fusion_query(
        "solid",
        {
            "id": "SAMPLE_1",
            "min_spanning_reads": 8,
            "fusion_effects": ["in-frame"],
            "fusion_callers": ["fusioncatcher"],
            "filter_genes": ["ALK"],
        },
    )

    assert query["calls"] == {
        "$elemMatch": {
            "effect": {"$regex": "^in-frame$", "$options": "i"},
            "$or": [{"caller": "fusioncatcher", "spanreads": {"$gte": 8}}],
        }
    }
    assert query["$or"] == [
        {"gene1": {"$in": ["ALK"]}},
        {"gene2": {"$in": ["ALK"]}},
    ]


def test_build_fusion_query_treats_non_in_frame_effects_as_out_of_frame() -> None:
    """Out-of-frame is a category covering every non-empty non-in-frame caller value."""
    query = build_fusion_query(
        "wts",
        {
            "id": "SAMPLE_1",
            "fusion_effects": ["out-of-frame"],
        },
    )

    assert query["calls"]["$elemMatch"]["effect"] == {
        "$regex": "^(?!in-frame$).+",
        "$options": "i",
    }


def test_build_fusion_query_omits_effect_predicate_when_both_categories_selected() -> None:
    """Selecting both display categories does not exclude any caller effect value."""
    query = build_fusion_query(
        "wts",
        {
            "id": "SAMPLE_1",
            "fusion_effects": ["in-frame", "out-of-frame"],
        },
    )

    assert query == {"SAMPLE_ID": "SAMPLE_1"}


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


def test_build_fusion_query_matches_selected_description_tokens() -> None:
    """Description filters match complete comma-delimited evidence terms."""
    query = build_fusion_query(
        "wts",
        {
            "id": "SAMPLE_1",
            "fusion_descriptions": ["known", "matched-normal"],
        },
    )

    clauses = query["calls"]["$elemMatch"]["$or"]
    assert clauses == [
        {
            "desc": {
                "$regex": r"(?:^|,\s*)known(?:\s*,|$)",
                "$options": "i",
            }
        },
        {
            "desc": {
                "$regex": r"(?:^|,\s*)matched\-normal(?:\s*,|$)",
                "$options": "i",
            }
        },
    ]


def test_build_fusion_query_combines_callers_and_descriptions_on_one_call() -> None:
    """Caller and evidence restrictions must be satisfied by the same call."""
    query = build_fusion_query(
        "wts",
        {
            "id": "SAMPLE_1",
            "fusion_callers": ["fusioncatcher"],
            "fusion_descriptions": ["oncogene"],
            "min_spanning_reads": 4,
        },
    )

    assert query["calls"]["$elemMatch"]["$and"] == [
        {
            "$or": [
                {"caller": "fusioncatcher", "spanreads": {"$gte": 4}},
            ]
        },
        {
            "$or": [
                {
                    "desc": {
                        "$regex": r"(?:^|,\s*)oncogene(?:\s*,|$)",
                        "$options": "i",
                    }
                }
            ]
        },
    ]


def test_build_fusion_query_normalizes_caller_aliases_before_matching() -> None:
    """Mongo predicates always use canonical caller keys, never UI display labels."""
    query = build_fusion_query(
        "wts",
        {
            "id": "SAMPLE_1",
            "fusion_callers": ["FusionCatcher", "fusioncaller_STAR-FUSION"],
        },
    )

    assert query["calls"]["$elemMatch"]["$or"] == [
        {"caller": "fusioncatcher"},
        {"caller": "starfusion"},
    ]


def test_fusion_policy_admission_uses_gene_pairs_without_changing_the_baseline() -> None:
    policy = _finding_policy(
        _finding_rule(
            rule_id="retain_kmt2a_aff1",
            mode="admit",
            criteria={"gene_pairs": ("KMT2A--AFF1",)},
        )
    )
    query = build_fusion_query(
        "solid",
        {
            "id": "SAMPLE_1",
            "asp_id": "rna_fusion",
            "subpanel_id": "base",
            "min_spanning_reads": 10,
        },
        policy=policy,
    )

    admission = query["$or"][1]
    assert {"gene1": "KMT2A", "gene2": "AFF1"} in admission["$or"]
    assert {"gene1": "AFF1", "gene2": "KMT2A"} in admission["$or"]


def test_translocation_policy_extends_gene_scope_and_then_excludes_matches() -> None:
    policy = _finding_policy(
        _finding_rule(
            rule_id="retain_bcr_abl1",
            mode="admit",
            criteria={"gene_pairs": ("ABL1--BCR",)},
        ),
        _finding_rule(
            rule_id="remove_artifact",
            mode="exclude",
            criteria={"genes": ("ARTIFACT",)},
        ),
    )
    rows = [
        {"_id": "panel", "INFO": {"SVTYPE": "BND", "ANN": [{"Gene_Name": "TP53&ALK"}]}},
        {"_id": "admitted", "INFO": {"SVTYPE": "BND", "ANN": [{"Gene_Name": "BCR&ABL1"}]}},
        {"_id": "excluded", "INFO": {"SVTYPE": "BND", "ANN": [{"Gene_Name": "TP53&ARTIFACT"}]}},
    ]
    settings = {"assay_group": "solid", "intent": "somatic"}

    query = build_transloc_query("SAMPLE_1", settings, policy=policy)
    filtered = filter_translocations_by_genes(
        rows,
        filter_genes=["TP53"],
        restricted=True,
        settings=settings,
        policy=policy,
    )

    assert "ARTIFACT" in str(query)
    assert [row["_id"] for row in filtered] == ["panel", "admitted"]
