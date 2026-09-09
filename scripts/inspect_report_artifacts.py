#!/usr/bin/env python3
"""Read-only report-artifact reconciliation; never modifies MongoDB or files."""

import argparse
import json
import os

from pymongo import MongoClient

from api.application.reporting.artifact_inventory import inspect_report_artifacts
from api.config.mongo import configured_mongo_uri


def main():
    """Compare report records with stored artifacts and print a read-only JSON inventory.

    Returns:
        One when records reference missing or outside-root files, otherwise zero.
        Output contains counts unless ``--details`` requests identifiers and paths.

    Raises:
        SystemExit: CLI parsing exits, the MongoDB URI is missing, or the minimum
            artifact age is negative.
        ValueError: The report root exists but is not a directory.
        OSError: Resolving the report root or inspecting artifact metadata fails.
        pymongo.errors.PyMongoError: Report records cannot be read from MongoDB.

    Notes:
        Converts the minimum age from hours to seconds; the default is 24 hours.
        Does not modify database records or artifact files and closes the client.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mongo-uri", default=configured_mongo_uri(os.environ, "primary"))
    parser.add_argument("--database", required=True)
    parser.add_argument("--reports-collection", default="reports")
    parser.add_argument("--reports-root", required=True)
    parser.add_argument("--minimum-age-hours", type=float, default=24)
    parser.add_argument(
        "--details", action="store_true", help="Include local report identifiers and relative paths"
    )
    args = parser.parse_args()
    if not args.mongo_uri:
        parser.error("--mongo-uri or COYOTE3_MONGO_URI is required")
    if args.minimum_age_hours < 0:
        parser.error("--minimum-age-hours must be nonnegative")
    with MongoClient(args.mongo_uri, serverSelectionTimeoutMS=5000) as client:
        records = client[args.database][args.reports_collection].find(
            {}, {"filepath": 1, "pdf_filepath": 1}
        )
        result = inspect_report_artifacts(
            args.reports_root, records, minimum_age_seconds=args.minimum_age_hours * 3600
        )
    print(
        json.dumps(
            result if args.details else {key: len(value) for key, value in result.items()}, indent=2
        )
    )
    return 1 if result["missing"] or result["outside_root"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
