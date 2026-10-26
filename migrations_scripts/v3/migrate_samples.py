#!/usr/bin/env python3
"""Convert Coyote3 v3 hematology samples and embedded history to current collections."""

import sys
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from migrations_scripts.common import command, finish_sample, normalize_scope, rename  # noqa: E402

ASSAYS = {"gmshem", "hema_gmsv1"}


def convert(source: dict, review: dict, assay_id: str) -> dict[str, list[dict]]:
    """Map recorded v3 hematology scope and externalize embedded sample history.

    Args:
        source: Original v3 sample with BSON identity and recorded provenance.
        review: Source-bound missing metadata and explicit canonical filters.
        assay_id: gmshem or hema_gmsv1, retained as the lowercase ASP identifier.

    Returns:
        Validated samples, sample_comments, reports and recorded embedded RNA collections.

    Raises:
        ValueError: Scope conflicts or historical metadata is insufficient.
        ValidationError: A destination record fails its current collection contract.
    """
    assay_id = assay_id.lower()
    if assay_id not in ASSAYS:
        raise ValueError("Only hematology assays are selected from v3")
    document = deepcopy(source)
    normalize_scope(document)
    groups = document.pop("groups", None)
    groups = [groups] if isinstance(groups, str) else groups
    if groups is not None and (
        not isinstance(groups, list) or [str(g).lower() for g in groups] != [assay_id]
    ):
        raise ValueError("v3 groups must identify exactly the selected assay")
    physical = document.pop("assay", None)
    if physical is not None and str(physical).lower() != assay_id:
        raise ValueError("v3 assay disagrees with selected physical ASP")
    if physical is None and groups is None:
        raise ValueError("v3 has no recorded physical assay identity")
    if document.get("asp_id") not in (None, assay_id):
        raise ValueError("Recorded asp_id conflicts with selected assay")
    document["asp_id"] = assay_id
    rename(document, "profile", "environment")
    rename(document, "subpanel", "diagnosis_id")
    rename(document, "subpanel_id", "diagnosis_id")
    rename(document, "omics_layer", "asp_category")
    rename(document, "sequencing_scope", "asp_family")
    if isinstance(document.get("asp_category"), str):
        document["asp_category"] = document["asp_category"].lower()
    family = str(document.get("asp_family", "")).lower()
    if family in {"panel", "wgs"} and document.get("asp_category") in {"dna", "rna"}:
        document["asp_family"] = f"{family}-{document['asp_category']}"
    if "sequencing_technology" in document:
        if not review.get("metadata", {}).get("platform"):
            raise ValueError("Map v3 sequencing_technology to verified platform metadata")
        document.pop("sequencing_technology")
    return finish_sample(source, document, review)


if __name__ == "__main__":
    raise SystemExit(command(3, ASSAYS, convert))
