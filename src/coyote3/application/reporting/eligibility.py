"""Explicit ASPC tier eligibility shared by previews, saved reports and rule tests."""

from coyote3.contracts.schemas.assay import ReportableTiersDoc


def reportable_tiers(reporting: dict, analysis: str) -> list[int]:
    """Read validated tier selections, retaining an explicitly empty selection.

    Args:
        reporting: ASPC reporting configuration.
        analysis: SNV or FUSION, the classification-driven finding types.

    Returns:
        Ordered allowed tiers. Missing settings use the contract's new-ASPC defaults.
    """
    policy = ReportableTiersDoc.model_validate(reporting.get("reportable_tiers", {}))
    return policy.model_dump()[analysis]


def classification_is_usable(classification: dict | None) -> bool:
    """Allow active classifications or inactive versions explicitly linked to this sample.

    Args:
        classification: Scoped classification; None has no usable interpretation.

    Returns:
        False for uncertain legacy fallbacks and unrelated inactive interpretations.
    """
    if not classification:
        return False
    return (
        classification.get("is_active", True)
        or classification.get("historical_sample_match") is True
    )
