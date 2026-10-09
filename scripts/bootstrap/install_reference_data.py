#!/usr/bin/env python3
"""Install bundled HGNC and VEP references into empty knowledgebase collections only."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pymongo import MongoClient  # noqa: E402

from api.config.loaders.collections import load_collection_section  # noqa: E402
from api.config.mongo import mongo_endpoints  # noqa: E402
from scripts.bootstrap.bootstrap_database import (  # noqa: E402
    DEFAULT_RBAC_DIR,
    DEFAULT_REFERENCE_DIR,
    _build_seed_documents,
    _insert_if_empty,
)
from scripts.knowledgebase.vep_diagram_storage import load_seed_diagrams  # noqa: E402


def install_references(database, *, actor: str, reference_dir: Path) -> None:
    """Load bundled references without overwriting populated collections or building indexes.

    Args:
        database: Explicit knowledgebase database handle.
        actor: Existing administrator username recorded in seed provenance.
        reference_dir: Bundled HGNC/VEP seed directory, including diagram files.

    Raises:
        ValueError: Seed documents do not satisfy their collection contracts.
        OSError: A seed file cannot be read.
    """
    seed = _build_seed_documents(
        rbac_dir=DEFAULT_RBAC_DIR,
        reference_dir=reference_dir,
        demo_center_dir=None,
        actor=actor.strip().lower(),
    )
    mapping = load_collection_section("knowledgebase")
    seed["vep_diagrams"] = load_seed_diagrams(seed["vep_metadata"], reference_dir)
    for name, key in (
        ("vep_diagrams", "vep_diagrams_collection"),
        ("hgnc_genes", "hgnc_collection"),
        ("vep_metadata", "vep_metadata_collection"),
    ):
        result = _insert_if_empty(database, mapping[key], seed[name])
        print(f"[{result}] knowledgebase reference: {name}")


def main() -> int:
    """Install bundled references using the configured knowledgebase endpoint.

    Returns:
        Zero when each bundled collection is loaded or preserved because it is populated.

    Raises:
        SystemExit: The required administrator username is missing or blank.
        RuntimeError: Endpoint configuration is incomplete or databases overlap.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actor", required=True, help="Existing administrator username")
    parser.add_argument("--reference-dir", type=Path, default=DEFAULT_REFERENCE_DIR)
    args = parser.parse_args()
    if not args.actor.strip():
        parser.error("--actor must not be blank")
    endpoint = mongo_endpoints(os.environ)["knowledgebase"]
    with MongoClient(endpoint.uri, serverSelectionTimeoutMS=7000) as client:
        install_references(
            client[endpoint.database], actor=args.actor, reference_dir=args.reference_dir
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
