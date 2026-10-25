"""Classification fallback preserves specificity and reporting confirmation boundaries."""

from types import SimpleNamespace

import mongomock
import pytest

from api.infra.mongo.repositories.annotations import AnnotationsRepository
from coyote3.application.interpretation.annotation_enrichment import add_global_annotations
from coyote3.domain.annotation_scope import annotation_scope_match


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
                "asp_group": group,
                "diagnosis_id": diagnosis,
                "class": tier,
                "time_created": created,
                "asp_id": assay,
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
    assert [row["asp_group"] for row in candidates] == ["parent", "root", "child"]
    assert candidates[0]["inheritance_distance"] == 1
    assert all(row["requires_retiering"] and not row["effective"] for row in candidates)
    assert not candidates[-1]["fallback_eligible"]
    enriched, report_candidates = add_global_annotations(
        [finding], "child", "mpn", annotation_repository=repository, sample_context=context
    )
    assert report_candidates == []
    assert enriched[0]["other_classification"][0]["asp_group"] == "parent"
    db.annotations.insert_one(
        {
            "gene": "TP53",
            "variant": "p.Arg1Gly",
            "hgvsp": "p.Arg1Gly",
            "nomenclature": "p",
            "namespace": "clinical",
            "asp_group": "child",
            "diagnosis_id": "mpn",
            "class": 4,
            "time_created": 0,
            "asp_id": context["assay_id"],
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
    annotation = {
        "asp_group": "child",
        "diagnosis_id": "base",
        "asp_id": context["assay_id"],
        "namespace": "clinical",
    }
    match = annotation_scope_match(
        annotation, group_path=["child", "parent"], diagnosis="mpn", context=context
    )
    assert match["match_level"] == "same_assay"
    assert match["fallback_eligible"] and match["requires_retiering"]
    annotation["diagnosis_id"] = "cll"
    assert not annotation_scope_match(
        annotation, group_path=["child", "parent"], diagnosis="mpn", context=context
    )["fallback_eligible"]


@pytest.mark.parametrize(
    "environment,expected_tier,expected_text",
    [
        ("production", 1, "Clinical explanation"),
        ("development", 2, "Sandbox explanation"),
        ("testing", 2, "Sandbox explanation"),
        ("validation", 2, "Sandbox explanation"),
    ],
)
def test_namespace_visibility_and_independent_text_resolution(
    environment, expected_tier, expected_text
):
    """Nonproduction shares annotations; broad text never supplies a reportable tier."""
    db = mongomock.MongoClient().test
    db.groups.insert_many(
        [
            {"group_id": "myeloid", "parent_group_id": "hematology"},
            {"group_id": "hematology"},
        ]
    )
    identity = {
        "variant": "p.Arg1Gly",
        "hgvsp": "p.Arg1Gly",
        "gene": "TP53",
        "nomenclature": "p",
        "diagnosis_id": "mpn",
    }
    for namespace, tier, text, created in [
        ("clinical", 1, "Clinical explanation", 1),
        ("sandboxed", 2, "Sandbox explanation", 2),
    ]:
        db.annotations.insert_one(
            {
                **identity,
                "asp_group": "myeloid",
                "asp_id": "demo-panel",
                "namespace": namespace,
                "class": tier,
                "time_created": created,
            }
        )
        db.annotations.insert_one(
            {
                **identity,
                "asp_group": "hematology",
                "asp_id": None,
                "namespace": namespace,
                "text": text,
                "time_created": created,
            }
        )
    repository = AnnotationsRepository(
        SimpleNamespace(
            annotations_collection=db.annotations,
            assay_groups_collection=db.groups,
        )
    )
    finding = {"INFO": {"selected_CSQ": {"SYMBOL": "TP53", "HGVSp": "p.Arg1Gly"}}}
    _, tier, _, texts = repository.get_global_annotations(
        finding,
        "myeloid",
        "mpn",
        sample_context={"assay_id": "demo-panel", "environment": environment},
    )
    assert tier["class"] == expected_tier
    assert texts["myeloid:mpn"]["text"] == expected_text
    assert repository.get_matching_annotation_text(tier) == expected_text
    db.annotations.insert_one(
        {
            **identity,
            "asp_group": "myeloid",
            "asp_id": "demo-panel",
            "namespace": "clinical",
            "text": "Exact explanation",
            "time_created": 0,
        }
    )
    assert repository.get_matching_annotation_text(tier) == "Exact explanation"
