"""Sample filter initialization and paired sample identifiers."""

from __future__ import annotations

from copy import deepcopy


def merge_sample_settings_with_assay_config(sample_doc: dict, assay_config_doc: dict) -> dict:
    """Replace sample filters with a copy of sample settings or assay defaults.

    Args:
        sample_doc: Sample document to mutate. Truthy filters take precedence;
            missing, null, or empty filters select assay defaults.
        assay_config_doc: Assay defaults; missing filters means an empty mapping,
            while an explicit null filters value is preserved.

    Returns:
        The same sample dictionary with deeply copied filters and without
        use_diagnosis_genelist. Individual filter fields are not merged.
    """
    filters_config = assay_config_doc.get("filters", {})
    sample_filters = sample_doc.get("filters", {})
    if not sample_filters:
        sample_doc["filters"] = deepcopy(filters_config)
    else:
        sample_doc["filters"] = deepcopy(sample_filters)
    sample_doc.pop("use_diagnosis_genelist", None)
    return sample_doc


def get_case_and_control_sample_ids(sample_doc: dict) -> dict:
    """Extract populated case and control identifiers from a sample.

    Args:
        sample_doc: Document with optional case_id and control_id values.

    Returns:
        A new dictionary with case and/or control keys for truthy identifiers.
        Missing, null, and other falsy identifiers are omitted.
    """
    sample_ids = {}
    case = sample_doc.get("case_id")
    control = sample_doc.get("control_id")
    if case:
        sample_ids["case"] = case
    if control:
        sample_ids["control"] = control
    return sample_ids
