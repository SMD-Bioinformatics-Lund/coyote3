"""Common annotation enrichment helpers for DNA/RNA analyte flows."""

from __future__ import annotations


def add_alt_class(
    variant: dict, assay_group: str, subpanel: str | None, *, annotation_repository
) -> dict:
    """
    Add alternative classifications to a variant/fusion entry.
    """
    additional_classifications = list(
        annotation_repository.get_additional_classifications(variant, assay_group, subpanel) or []
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
    variants: list, assay_group: str, subpanel: str | None, *, annotation_repository
) -> tuple[list, list]:
    """
    Add global annotation/classification fields and collect selected entities.
    """
    selected_variants = []
    for var_idx, var in enumerate(variants):
        (
            variants[var_idx]["global_annotations"],
            variants[var_idx]["classification"],
            variants[var_idx]["other_classification"],
            variants[var_idx]["annotations_interesting"],
        ) = annotation_repository.get_global_annotations(var, assay_group, subpanel)
        classification = variants[var_idx]["classification"]
        if classification is not None:
            class_value = classification.get("class")
            if (
                class_value is not None
                and class_value < 999
                and not var.get("blacklist")
                and not var.get("fp")
                and not var.get("irrelevant")
            ):
                selected_variants.append(variants[var_idx])

        variants[var_idx] = add_alt_class(
            variants[var_idx], assay_group, subpanel, annotation_repository=annotation_repository
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
