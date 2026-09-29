"""Explicit ASPC tier eligibility shared by previews, saved reports and rule tests."""

from api.contracts.schemas.assay import ReportableTiersDoc


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
