#!/usr/bin/env python3
"""Build a normalized seed bundle for collection bootstrap."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.infra.seed.bundle import (  # noqa: E402
    canonicalize_seed_contract,
    load_reference_seed_pack,
    load_seed,
    lower_business_keys,
    stamp_docs,
)


def parse_args() -> argparse.Namespace:
    """Parse seed source, output directory, audit stamps, and reference pack paths.

    Returns:
        Process options with reference directories retained in command-line order.

    Raises:
        SystemExit: Required options are missing, arguments are invalid, or help is requested.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-source", required=True, help="Directory with *.json seed files")
    parser.add_argument("--dest-dir", required=True, help="Output directory for normalized seed")
    parser.add_argument("--seed-actor", required=True, help="created_by/updated_by stamp value")
    parser.add_argument("--seed-time", required=True, help="created_on/updated_on stamp value")
    parser.add_argument(
        "--reference-seed-data",
        action="append",
        default=[],
        help="Reference seed directory; repeat for RBAC and compressed reference packs",
    )
    return parser.parse_args()


def main() -> int:
    """Write normalized, stamped JSON seed files to the selected destination.

    Returns:
        Zero after writing every collection and printing the destination.

    Raises:
        SystemExit: CLI parsing exits, a source directory is missing, or seed values
            are not arrays or reference lines are not objects.
        ValueError: Seed JSON is malformed or normalization rejects a contract field.
        OSError: Reading sources or creating and writing the destination fails.

    Notes:
        Later reference packs replace earlier collections. Output files overwrite
        matching filenames; unrelated destination files are retained.
    """
    args = parse_args()
    source = Path(args.seed_source)
    dest_dir = Path(args.dest_dir)
    reference_seed_data = [Path(value) for value in args.reference_seed_data]

    if not source.is_dir():
        raise SystemExit(f"Seed source not found: {source}")
    dest_dir.mkdir(parents=True, exist_ok=True)

    seed = load_seed(source)
    for reference_dir in reference_seed_data:
        if not reference_dir.is_dir():
            raise SystemExit(f"Reference seed source not found: {reference_dir}")
        seed.update(load_reference_seed_pack(reference_dir))
    canonicalize_seed_contract(seed)
    lower_business_keys(seed)
    stamp_docs(seed, args.seed_actor, args.seed_time)

    for collection, docs in seed.items():
        (dest_dir / f"{collection}.json").write_text(
            json.dumps(docs, ensure_ascii=False), encoding="utf-8"
        )

    print(f"[ok] normalized seed bundle: {dest_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
