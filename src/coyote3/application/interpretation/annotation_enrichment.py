"""Common annotation enrichment helpers for DNA/RNA analyte flows."""

from __future__ import annotations

from coyote3.application.reporting.eligibility import classification_is_usable
from coyote3.domain.rna.helpers import get_selected_fusioncall


def add_alt_class(
    variant: dict,
    assay_group: str,
    diagnosis: str | None,
    *,
    annotation_repository,
    sample_context: dict | None = None,
) -> dict:
    """
    Add alternative classifications to a variant/fusion entry.
    """
    additional_classifications = list(
        annotation_repository.get_additional_classifications(
            variant, assay_group, diagnosis, sample_context=sample_context
        )
        or []
    )
    if additional_classifications:
        additional_classifications[0].pop("author", None)
        additional_classifications[0].pop("time_created", None)
        class_value = _classification_value(additional_classifications[0].get("class"))
        if class_value is None:
            variant["additional_classification"] = None
        else:
            additional_classifications[0]["class"] = class_value
            variant["additional_classification"] = additional_classifications[0]
    else:
        variant["additional_classification"] = None

    return variant


def add_global_annotations(
    variants: list,
    assay_group: str,
    diagnosis: str | None,
    *,
    annotation_repository,
    sample_context: dict | None = None,
) -> tuple[list, list]:
    """Attach matched annotations and collect eligible tiered findings.

    Fusion matching uses the selected call's identity with the parent sample ID,
    as in the fusion detail view, without flattening or changing the stored calls.

    Args:
        variants: Finding records to enrich in place.
        assay_group: Biological group used for annotation scope matching.
        diagnosis: Current diagnosis; None selects the base diagnosis scope.
        annotation_repository: Repository providing scoped annotation lookups.
        sample_context: Resolved assay and environment; None cannot establish
            an effective classification.

    Returns:
        Enriched findings and the subset with usable tiers and no exclusion flags.
    """
    selected_variants = []
    for var_idx, var in enumerate(variants):
        annotation_identity = (
            {**(get_selected_fusioncall(var) or {}), "SAMPLE_ID": var.get("SAMPLE_ID")}
            if "calls" in var
            else var
        )
        (
            variants[var_idx]["global_annotations"],
            variants[var_idx]["classification"],
            variants[var_idx]["other_classification"],
            variants[var_idx]["annotations_interesting"],
        ) = annotation_repository.get_global_annotations(
            annotation_identity, assay_group, diagnosis, sample_context=sample_context
        )
        classification = variants[var_idx]["classification"]
        if classification is not None:
            class_value = classification.get("class")
            if (
                class_value is not None
                and class_value < 999
                and classification_is_usable(classification)
                and not var.get("blacklist")
                and not var.get("fp")
                and not var.get("irrelevant")
            ):
                selected_variants.append(variants[var_idx])

        variants[var_idx] = add_alt_class(
            variants[var_idx],
            assay_group,
            diagnosis,
            annotation_repository=annotation_repository,
            sample_context=sample_context,
        )
    return variants, selected_variants


def _classification_value(value) -> int | None:
    """Return a numeric classification value when one exists."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
