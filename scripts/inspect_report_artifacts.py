#!/usr/bin/env python3
"""Read-only report-artifact reconciliation; never modifies MongoDB or files."""

import argparse
import json
import os

from pymongo import MongoClient

from api.application.reporting.artifact_inventory import inspect_report_artifacts
from api.config.mongo import configured_mongo_uri


def main():
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
