"""Classification fallback preserves specificity and reporting confirmation boundaries."""

from coyote.domain.annotation_scope import annotation_scope_match


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
