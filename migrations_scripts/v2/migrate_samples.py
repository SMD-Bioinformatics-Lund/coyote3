#!/usr/bin/env python3
"""Convert Coyote v2 samples and their embedded history to current MongoDB collections."""

import sys
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from migrations_scripts.common import (  # noqa: E402
    command,
    finish_sample,
    normalize_scope,
    rename,
    v2_assay_identity,
)

ASSAYS = {
    "hema_gmsv1",
    "parp_inhib",
    "fusion",
    "fusion_validation_nf",
    "lymph_gmsv3",
    "lymphoid_gmsv1",
    "myeloid_gmsv1",
    "solidrna_gmsv5",
    "solid_gmsv3",
    "tumwgs",
    "tumwgs-hema",
    "tumwgs-solid",
    "twistrnafusionv1-0",
}


def convert(source: dict, review: dict, assay_id: str) -> dict[str, list[dict]]:
    """Map v2 scope fields and externalize its sample-owned embedded documents.

    Args:
        source: Original v2 sample with BSON identity and creation timestamp.
        review: Source-bound missing metadata and explicit canonical filter mapping.
        assay_id: One supported v2 assay, including split tumwgs scope.

    Returns:
        Validated samples, sample_comments, reports and recorded embedded RNA collections.

    Raises:
        ValueError: Source scope conflicts or required historical evidence is absent.
        ValidationError: A destination record fails its collection contract.
    """
    assay_id = assay_id.lower()
    if assay_id not in ASSAYS:
        raise ValueError("Unsupported v2 assay")
    expected = "tumwgs" if assay_id.startswith("tumwgs-") else assay_id
    if v2_assay_identity(source) != expected:
        raise ValueError("v2 groups or older assay must identify exactly the selected assay")
    document = deepcopy(source)
    if assay_id.startswith("tumwgs-"):
        recorded = document.get("subpanel", document.get("diagnosis_id"))
        if str(recorded).lower() != assay_id.removeprefix("tumwgs-"):
            raise ValueError("tumwgs subpanel disagrees with the selected assay")
    normalize_scope(document, unspecified_diagnosis="legacy" if assay_id == "tumwgs" else "base")
    document.pop("groups", None)
    document.pop("group", None)
    if document.get("asp_id") not in (None, assay_id):
        raise ValueError("Recorded asp_id conflicts with selected assay")
    document["asp_id"] = assay_id
    document.pop("assay", None)
    rename(document, "profile", "environment")
    rename(document, "omics_layer", "asp_category")
    rename(document, "sequencing_scope", "asp_family")
    rename(document, "subpanel", "diagnosis_id")
    if assay_id == "tumwgs":
        if str(document.get("diagnosis_id") or "").strip().lower() not in {"", "none", "legacy"}:
            raise ValueError("Use the matching split assay for a recorded tumwgs subpanel")
        document["diagnosis_id"] = "legacy"
    if "sequencing_technology" in document:
        if not review.get("metadata", {}).get("platform"):
            raise ValueError("Map v2 sequencing_technology to verified platform metadata")
        document.pop("sequencing_technology")
    return finish_sample(source, document, review)


if __name__ == "__main__":
    raise SystemExit(command(2, ASSAYS, convert))
