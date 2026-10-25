"""Select the operator-approved legacy assays without changing sample identities."""

from copy import deepcopy

ASSAY_SOURCES = {
    "gmshem": 3,
    "hema_gmsv1": 3,
    "parp_inhib": 2,
    "fusion": 2,
    "fusion_validation_nf": 2,
    "lymph_gmsv3": 2,
    "lymphoid_gmsv1": 2,
    "myeloid_gmsv1": 2,
    "solidrna_gmsv5": 2,
    "solid_gmsv3": 2,
    "tumwgs-hema": 2,
    "tumwgs-solid": 2,
    "twistrnafusionv1-0": 2,
}


def validate_assay(assay_id: str, version: int) -> str:
    """Return the lowercase supported assay or reject the wrong source version.

    Args:
        assay_id: One destination assay identifier; tumwgs requires its hema/solid suffix.
        version: Legacy source major version, either 2 or 3.

    Returns:
        Lowercase destination ASP identifier.

    Raises:
        ValueError: The identifier is unsupported or belongs to the other source.
    """
    normalized = assay_id.lower()
    if ASSAY_SOURCES.get(normalized) != version:
        raise ValueError("Select one supported assay from its designated source version")
    return normalized


def sample_assay(sample: dict, field: str) -> str:
    """Read one explicitly named legacy assay field and split recorded tumwgs subpanels.

    Args:
        sample: Unmodified source sample.
        field: Exact source field containing the operator's listed assay identifiers.

    Returns:
        Lowercase destination identifier, or an empty string for a missing source value.

    Raises:
        ValueError: A tumwgs sample has no supported recorded hema/solid subpanel.
    """
    value = sample.get(field)
    if not isinstance(value, str):
        return ""
    identifier = value.lower()
    if identifier == "tumwgs":
        diagnosis = sample.get("subpanel")
        if not isinstance(diagnosis, str) or diagnosis.lower() not in {"hema", "solid"}:
            raise ValueError("Legacy tumwgs requires a recorded hema or solid subpanel")
        identifier += "-" + diagnosis.lower()
    return identifier


def matches_assay(sample: dict, field: str, assay_id: str) -> bool:
    """Select one assay without reconciling unrelated samples from the export.

    Args:
        sample: Unmodified source sample.
        field: Explicit historical assay field.
        assay_id: Supported lowercase destination identifier.

    Returns:
        Whether the sample belongs to the requested assay and tumwgs subpanel.

    Raises:
        ValueError: A relevant tumwgs sample has an unresolved subpanel.
    """
    raw = sample.get(field)
    expected = "tumwgs" if assay_id in {"tumwgs-hema", "tumwgs-solid"} else assay_id
    if not isinstance(raw, str) or raw.lower() != expected:
        return False
    return sample_assay(sample, field) == assay_id


def prepare_scope(document: dict, metadata: dict, *, assay_id: str, field: str) -> dict:
    """Apply the selected assay and recorded diagnosis using installed ASP group metadata.

    Args:
        document: Prepared sample copy, retaining its original BSON identity.
        metadata: Reviewed installed ASPC context, including asp_group.
        assay_id: Lowercase assay selected by the operator.
        field: Legacy field already verified against the selection.

    Returns:
        Sample copy with lowercase canonical scope and legacy scope fields removed.

    Raises:
        ValueError: Installed scope disagrees with the historical assay or diagnosis.
    """
    result = deepcopy(document)
    if metadata.get("asp_id") != assay_id or not metadata.get("asp_group"):
        raise ValueError("Selected ASPC must match the selected assay and supply asp_group")
    diagnoses = [
        value.lower() if isinstance(value, str) else value
        for key in ("subpanel", "subpanel_id", "diagnosis_id")
        if (value := result.get(key)) is not None
    ]
    if diagnoses and any(value != diagnoses[0] for value in diagnoses):
        raise ValueError("Legacy sample diagnosis fields conflict")
    if diagnoses and diagnoses[0] != metadata.get("diagnosis_id"):
        raise ValueError("Selected ASPC diagnosis differs from the recorded subpanel")
    if field != "asp_id":
        result.pop(field, None)
    for key in ("assay", "subpanel", "subpanel_id"):
        result.pop(key, None)
    for key in ("asp_id", "asp_group", "diagnosis_id"):
        value = metadata.get(key)
        if isinstance(value, str) and value != value.lower():
            raise ValueError("Installed target scope identifiers must be lowercase")
        if key in result and result[key] is not None:
            existing = result[key].lower() if isinstance(result[key], str) else result[key]
            if existing != value:
                raise ValueError("Recorded sample scope conflicts with installed configuration")
        result[key] = value
    return result
