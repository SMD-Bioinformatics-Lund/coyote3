#!/usr/bin/env python3
"""Convert v3 non-variant sample collections and preserved report findings."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from migrations_scripts.related import (  # noqa: E402
    COVERAGE_COLLECTIONS,
    convert_record,
    coverage_destination,
    run,
)

COLLECTIONS = {
    "cnvs": "cnvs",
    "transloc": "translocations",
    "biomarkers": "biomarkers",
    # These source collections may mix measurement and exclusion formats.
    "panel_cov": "by_document_shape",
    "group_coverage": "by_document_shape",
    "coverage": "by_document_shape",
    "fusions": "fusions",
    "pgx": "pgx",
    "rna_expression": "rna_expression",
    "rna_qc": "rna_qc",
    "rna_classification": "rna_classification",
    "reported_variants": "reported_variants",
}


def convert(
    source: dict, collection: str, sample: dict, context: dict, review: dict | None = None
) -> dict[str, list[dict]]:
    """Convert one v3 source record using its reviewed physical collection mapping.

    Args:
        source: Original record with its unchanged BSON identity.
        collection: One explicitly listed non-variant v3 source collection.
        sample: Prepared owning sample.
        context: Verified reports and comments for report-finding parent checks.
        review: Optional digest-bound missing metadata.

    Returns:
        Contract-validated current records and any extracted finding comments.

    Raises:
        ValueError: Collection selection or related references are invalid.
        ValidationError: Current contracts reject the converted evidence.
    """
    if collection not in COLLECTIONS:
        raise ValueError("Select an allowed v3 related collection")
    destination = (
        coverage_destination(source)
        if collection in COVERAGE_COLLECTIONS
        else COLLECTIONS[collection]
    )
    return convert_record(source, destination, sample, context, review)


if __name__ == "__main__":
    raise SystemExit(run(3, COLLECTIONS, convert))
