"""Explicit ASPC tier eligibility shared by previews, saved reports and rule tests."""

from coyote3.contracts.schemas.assay import ReportableTiersDoc


def reportable_tiers(reporting: dict, analysis: str) -> list[int]:
    """Read validated tier selections, retaining an explicitly empty selection.

    Args:
        reporting: ASPC reporting configuration.
        analysis: SNV, FUSION, CNV or TRANSLOCATION finding type.

    Returns:
        Ordered allowed tiers. Missing settings use the contract's new-ASPC defaults.
    """
    policy = ReportableTiersDoc.model_validate(reporting.get("reportable_tiers", {}))
    return policy.model_dump()[analysis]


def structural_report_inclusion(finding: dict, allowed_tiers: list[int]) -> bool:
    """Include an explicitly selected structural finding or a usable allowed tier.

    Args:
        finding: Scope-hydrated finding with review flags and classification.
        allowed_tiers: ASPC tier selection; empty disables automatic tier inclusion.

    Returns:
        Whether review state and explicit selection or tier allow report inclusion.
        False-positive and irrelevant flags always exclude the finding.
    """
    if finding.get("fp") or finding.get("irrelevant"):
        return False
    classification = finding.get("classification") or {}
    return bool(finding.get("interesting")) or bool(
        not finding.get("blacklist")
        and classification_is_usable(classification)
        and classification.get("class") in allowed_tiers
    )


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
