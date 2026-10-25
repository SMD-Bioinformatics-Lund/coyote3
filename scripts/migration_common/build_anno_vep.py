#!/usr/bin/env python3
"""Build shared VEP evidence from complete offline v2/v3 variant indexes."""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import ExitStack
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.migration_common.offline import (  # noqa: E402
    RecordConversionError,
    SourceIndex,
    private_json,
    read_json,
)
from scripts.migration_common.prepare_references import verify_reference_snapshot  # noqa: E402
from scripts.migration_common.schema_inventory import verify_review  # noqa: E402
from scripts.migration_common.target_catalog import validate_snapshot  # noqa: E402
from scripts.migration_common.vep import build_vep_reference  # noqa: E402


def main() -> int:
    """Validate export reviews and build bounded reference bundles without MongoDB."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        nargs=4,
        action="append",
        required=True,
        metavar=("VERSION", "INDEX", "REVIEW", "SCHEMA_AUDIT"),
        help="Repeat for each v2/v3 index and its completed, reviewed schema audit",
    )
    parser.add_argument("--vep-version", required=True)
    parser.add_argument("--target-catalog", type=Path, required=True)
    parser.add_argument("--reference-catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--issues", type=Path)
    args = parser.parse_args()
    try:
        catalog = read_json(args.target_catalog)
        validate_snapshot(catalog)
        references = verify_reference_snapshot(args.reference_catalog, args.vep_version)
        with ExitStack() as stack:
            sources = []
            for version, index, review_path, audit in args.source:
                if version not in {"2", "3"}:
                    raise ValueError("Source version must be 2 or 3")
                source = SourceIndex(Path(index), int(version))
                stack.callback(source.close)
                review = read_json(Path(review_path))
                verify_review(source, Path(audit), review)
                sources.append((source, review))
            manifest = build_vep_reference(
                sources,
                args.output,
                version=args.vep_version,
                target_sha256=catalog["sha256"],
                batch_size=args.batch_size,
                references=references,
            )
        print(json.dumps(manifest["counts"]))
        return 0
    except Exception as error:
        print(f"Offline VEP build stopped: {type(error).__name__}", file=sys.stderr)
        if isinstance(error, RecordConversionError) and args.issues:
            private_json(args.issues, error.issue)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
