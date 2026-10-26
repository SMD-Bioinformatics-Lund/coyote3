#!/usr/bin/env python3
"""Convert v2 non-variant sample collections and their embedded finding comments."""

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
    "cnvs_wgs": "cnvs",
    "transloc": "translocations",
    "biomarkers": "biomarkers",
    "fusions": "fusions",
    "coverage": "by_document_shape",
    "pgx": "pgx",
    "rna_expression": "rna_expression",
    "rna_qc": "rna_qc",
    "rna_classification": "rna_classification",
    "reported_variants": "reported_variants",
}


def convert(
    source: dict, collection: str, sample: dict, context: dict, review: dict | None = None
) -> dict[str, list[dict]]:
    """Convert one v2 source record using its explicitly registered physical collection.

    Args:
        source: Original record retaining its BSON identity.
        collection: One non-variant v2 collection listed in COLLECTIONS.
        sample: Prepared owning sample.
        context: Verified reports and sample comments from its prepared bundle.
        review: Optional source-bound missing-field additions.

    Returns:
        Current related records plus extracted finding comments when present.

    Raises:
        ValueError: Collection selection or coverage shape is invalid.
        ValidationError: Source data cannot satisfy current clinical contracts.
    """
    if collection not in COLLECTIONS:
        raise ValueError("Select an allowed v2 related collection")
    destination = (
        coverage_destination(source)
        if collection in COVERAGE_COLLECTIONS
        else COLLECTIONS[collection]
    )
    return convert_record(source, destination, sample, context, review)


if __name__ == "__main__":
    raise SystemExit(run(2, COLLECTIONS, convert))
