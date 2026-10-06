#!/usr/bin/env python3
"""Move HGNC/VEP references and retire the superseded assay subpanel collection."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from bson import BSON
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.config.loaders.collections import load_collection_section  # noqa: E402
from api.config.mongo import configured_mongo_uri  # noqa: E402
from scripts.knowledgebase.migrate_knowledgebase_database import (  # noqa: E402
    assert_distinct_databases,
    copy_indexes,
    migrate_collection,
    verify_pair,
)


def validate_legacy_subpanels(source) -> int:
    """Require every current named legacy scope to have a current replacement.

    Args:
        source: Application database with old and new registries.

    Returns:
        Number of legacy documents, including superseded revisions.

    Raises:
        ValueError: A current scope has no shared definition or assay association.
    """
    mapping = load_collection_section("primary")
    for row in source.assay_subpanels.find({"is_current": True}):
        key = row.get("subpanel_id")
        if key in (None, "", "base"):
            continue
        definition = source[mapping["subpanels_collection"]].find_one(
            {"subpanel_id": key, "is_current": True}
        )
        association = source[mapping["subpanel_associations_collection"]].find_one(
            {"subpanel_id": key, "asp_id": row.get("asp_id"), "is_current": True}
        )
        if definition is None or association is None:
            raise ValueError(
                "Legacy subpanel has no current replacement; run subpanel migration first"
            )
    return source.assay_subpanels.count_documents({})


def migrate(source, target, *, apply=False, backup_dir: Path | None = None) -> dict:
    """Copy verified references before removing old collections.

    Args:
        source: Application database. Pause application and reference writers first.
        target: Knowledgebase database; may be on a different deployment.
        apply: Perform writes only when True; otherwise inspect counts and conflicts.
        backup_dir: New directory for BSON originals and collection/index metadata.

    Returns:
        Collection counts and verification results, without document contents.

    Raises:
        ValueError: Namespaces overlap, replacements are missing, or no backup is supplied.
        FileExistsError: The backup directory already exists.
        RuntimeError: A destination differs or content verification fails.

    Notes:
        Copy/rename/drop across deployments cannot be one transaction. Reruns verify
        existing targets and never replace conflicting data. Original BSON backups
        retain legacy revisions; only current scopes are checked for replacement.
    """
    assert_distinct_databases(source, target)
    legacy_count = validate_legacy_subpanels(source)
    mapping = load_collection_section("knowledgebase")
    references = {key: mapping[key] for key in ("hgnc_collection", "vep_metadata_collection")}
    plans = [
        migrate_collection(source, target, key, name, apply=False)
        for key, name in references.items()
    ]
    if not apply:
        return {"legacy_documents": legacy_count, "references": plans}
    if backup_dir is None:
        raise ValueError("--backup-dir is required for writes")
    backup_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
    names = set(source.list_collection_names())
    for name in [*references.values(), "assay_subpanels"]:
        if name not in names:
            continue
        with os.fdopen(
            os.open(backup_dir / f"{name}.bson", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
        ) as handle:
            for row in source[name].find({}):
                handle.write(BSON.encode(row))
            handle.flush()
            os.fsync(handle.fileno())
        metadata = {"options": source[name].options(), "indexes": list(source[name].list_indexes())}
        with os.fdopen(
            os.open(
                backup_dir / f"{name}.metadata.bson", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            ),
            "wb",
        ) as handle:
            handle.write(BSON.encode(metadata))
            handle.flush()
            os.fsync(handle.fileno())
    results = [
        migrate_collection(source, target, key, name, apply=True)
        for key, name in references.items()
    ]
    for key, name in references.items():
        if name in names:
            copy_indexes(source[name], target[name])
            if not verify_pair(source[name], target[name], key)["verified"]:
                raise RuntimeError("Reference verification failed; sources retained")
    validate_legacy_subpanels(source)
    for name in [*references.values(), "assay_subpanels"]:
        if name in names:
            source.drop_collection(name)
    return {"legacy_documents": legacy_count, "references": results, "sources_removed": True}


def main() -> int:
    """Run against explicitly configured application and knowledgebase endpoints."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-dir", type=Path)
    args = parser.parse_args()
    source_uri = configured_mongo_uri(os.environ, "primary")
    target_uri = configured_mongo_uri(os.environ, "knowledgebase")
    source_name = os.environ.get("COYOTE3_DB", "")
    target_name = os.environ.get("KNOWLEDGEBASE_DB", "")
    if not all((source_uri, target_uri, source_name, target_name)):
        parser.error("Configure COYOTE3 and KNOWLEDGEBASE URI/database variables")
    source_client = MongoClient(source_uri, serverSelectionTimeoutMS=7000)
    target_client = (
        source_client
        if source_uri == target_uri
        else MongoClient(target_uri, serverSelectionTimeoutMS=7000)
    )
    try:
        print(
            migrate(
                source_client[source_name],
                target_client[target_name],
                apply=args.apply,
                backup_dir=args.backup_dir,
            )
        )
    finally:
        if target_client is not source_client:
            target_client.close()
        source_client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
