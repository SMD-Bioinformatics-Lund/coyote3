"""Classification fallback preserves specificity and reporting confirmation boundaries."""

from types import SimpleNamespace

import mongomock

from api.application.interpretation.annotation_enrichment import add_global_annotations
from api.domain.core.annotation_scope import annotation_scope_match
from api.infra.mongo.repositories.annotations import AnnotationsRepository


def test_parent_classification_is_ranked_without_becoming_reportable():
    """A nearer parent wins over newer distant evidence; an exact match remains effective."""
    db = mongomock.MongoClient().test
    db.groups.insert_many(
        [
            {"group_id": "child", "parent_group_id": "parent"},
            {"group_id": "parent", "parent_group_id": "root"},
            {"group_id": "root"},
        ]
    )
    context = {"assay_id": "demo-panel", "environment": "production"}
    for group, assay, diagnosis, tier, created in [
        ("parent", "demo-other", "mpn", 2, 1),
        ("root", "demo-other", "mpn", 1, 3),
        ("child", "demo-panel", "cll", 3, 4),
    ]:
        db.annotations.insert_one(
            {
                "gene": "TP53",
                "variant": "p.Arg1Gly",
                "hgvsp": "p.Arg1Gly",
                "nomenclature": "p",
                "namespace": "clinical",
                "assay": group,
                "diagnosis": diagnosis,
                "class": tier,
                "time_created": created,
                "resource_context": {**context, "assay_id": assay},
            }
        )
    repository = AnnotationsRepository(
        SimpleNamespace(
            annotations_collection=db.annotations,
            assay_groups_collection=db.groups,
        )
    )
    finding = {"INFO": {"selected_CSQ": {"SYMBOL": "TP53", "HGVSp": "p.Arg1Gly"}}}
    _, accepted, candidates, _ = repository.get_global_annotations(
        finding,
        "child",
        "mpn",
        sample_context=context,
    )
    assert accepted == {"class": 999}
    assert [row["assay"] for row in candidates] == ["parent", "root", "child"]
    assert candidates[0]["inheritance_distance"] == 1
    assert all(row["requires_retiering"] and not row["effective"] for row in candidates)
    assert not candidates[-1]["fallback_eligible"]
    enriched, report_candidates = add_global_annotations(
        [finding], "child", "mpn", annotation_repository=repository, sample_context=context
    )
    assert report_candidates == []
    assert enriched[0]["other_classification"][0]["assay"] == "parent"
    db.annotations.insert_one(
        {
            "gene": "TP53",
            "variant": "p.Arg1Gly",
            "hgvsp": "p.Arg1Gly",
            "nomenclature": "p",
            "namespace": "clinical",
            "assay": "child",
            "diagnosis": "mpn",
            "class": 4,
            "time_created": 0,
            "resource_context": context,
        }
    )
    assert (
        repository.get_global_annotations(finding, "child", "mpn", sample_context=context)[1][
            "class"
        ]
        == 4
    )


def test_same_assay_broad_diagnosis_requires_confirmation():
    """Base is fallback, while another specific diagnosis is reference-only."""
    context = {"assay_id": "demo-panel", "environment": "production"}
    annotation = {"assay": "child", "diagnosis": "base", "resource_context": context}
    match = annotation_scope_match(
        annotation, group_path=["child", "parent"], diagnosis="mpn", context=context
    )
    assert match["match_level"] == "same_assay"
    assert match["fallback_eligible"] and match["requires_retiering"]
    annotation["diagnosis"] = "cll"
    assert not annotation_scope_match(
        annotation, group_path=["child", "parent"], diagnosis="mpn", context=context
    )["fallback_eligible"]
