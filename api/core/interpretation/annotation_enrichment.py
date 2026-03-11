
"""
Shared annotation enrichment helpers for DNA/RNA analyte flows.
"""

from api.infra.repositories.core_store_mongo import MongoCoreStoreRepository


_core_repo_instance: MongoCoreStoreRepository | None = None


def _core_repo() -> MongoCoreStoreRepository:
    global _core_repo_instance
    if _core_repo_instance is None:
        _core_repo_instance = MongoCoreStoreRepository()
    return _core_repo_instance


def add_alt_class(variant: dict, assay: str, subpanel: str) -> dict:
    """
    Add alternative classifications to a variant/fusion entry.
    """
    additional_classifications = _core_repo().annotation_handler.get_additional_classifications(
        variant, assay, subpanel
    )
    if additional_classifications:
        additional_classifications[0].pop("author", None)
        additional_classifications[0].pop("time_created", None)
        additional_classifications[0]["class"] = int(additional_classifications[0]["class"])
        variant["additional_classification"] = additional_classifications[0]
    else:
        variant["additional_classification"] = None

    return variant


def add_global_annotations(variants: list, assay: str, subpanel: str) -> tuple[list, list]:
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
        ) = _core_repo().annotation_handler.get_global_annotations(var, assay, subpanel)
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

        variants[var_idx] = add_alt_class(variants[var_idx], assay, subpanel)
    return variants, selected_variants
