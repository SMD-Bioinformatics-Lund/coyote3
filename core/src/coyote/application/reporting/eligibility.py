# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Explicit ASPC tier eligibility shared by previews, saved reports and rule tests."""

from coyote.contracts.schemas.assay import ReportableTiersDoc


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
    """Return whether a scoped classification is present.

    Annotation documents are immutable. Scope matching and reportable-tier
    selection are checked by the caller; there is no annotation lifecycle flag.
    """
    return bool(classification)
