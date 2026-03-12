#!/usr/bin/env python3
"""
Backfill business-key fields and enforce unique partial indexes collection-by-collection.

This script is idempotent and safe to run repeatedly.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any

from pymongo import MongoClient
from pymongo.errors import OperationFailure, PyMongoError


@dataclass(frozen=True)
class Rule:
    """Provide the rule type.
    """
    collection_names: tuple[str, ...]
    key_field: str


RULES: tuple[Rule, ...] = (
    Rule(("users", "users_beta2"), "user_id"),
    Rule(("roles", "roles_beta2"), "role_id"),
    Rule(("permissions", "permissions_beta2"), "permission_id"),
    Rule(("schemas", "schemas_beta2"), "schema_id"),
    Rule(("assay_specific_panels",), "asp_id"),
    Rule(("asp_configs",), "aspc_id"),
    Rule(("insilico_genelists", "insilico_genelists_beta2", "insilico_genelist_beta2"), "isgl_id"),
    Rule(("samples",), "sample_id"),
    Rule(("variants",), "variant_id"),
    Rule(("cnvs", "cnvs_wgs"), "cnv_id"),
    Rule(("translocations", "transloc"), "transloc_id"),
    Rule(("fusions",), "fusion_id"),
    Rule(("annotation",), "annotation_id"),
    Rule(("reported_variants",), "reported_variant_id"),
    Rule(("group_coverage",), "group_region_id"),
    Rule(("blacklist",), "blacklist_entry_id"),
    Rule(("biomarkers",), "biomarker_id"),
    Rule(("rna_expression",), "rna_expression_id"),
    Rule(("rna_classification",), "rna_classification_id"),
    Rule(("rna_qc",), "rna_qc_id"),
)


def parse_args() -> argparse.Namespace:
    """Handle parse args.

    Returns:
        argparse.Namespace: The function result.
    """
    parser = argparse.ArgumentParser(description="Backfill business keys for Coyote3 collections.")
    parser.add_argument("--mongo-uri", default="mongodb://localhost:27017")
    parser.add_argument("--db", action="append", dest="dbs", required=True, help="Target DB name; repeatable")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _normalize(value: Any, lowercase: bool = False) -> str | None:
    """Handle  normalize.

    Args:
            value: Value.
            lowercase: Lowercase. Optional argument.

    Returns:
            The  normalize result.
    """
    if value is None:
        return None
    normalized = str(value).strip()
    if lowercase:
        normalized = normalized.lower()
    return normalized or None


def _resolve_business_key(doc: dict[str, Any], key_field: str) -> str | None:
    """Handle  resolve business key.

    Args:
            doc: Doc.
            key_field: Key field.

    Returns:
            The  resolve business key result.
    """
    lower = key_field in {"role_id"}
    existing = _normalize(doc.get(key_field), lowercase=lower)
    if existing:
        return existing
    for src in ("_id", "username", "email", "name"):
        candidate = _normalize(doc.get(src), lowercase=lower)
        if candidate:
            return candidate
    return None


def backfill_collection(col, key_field: str, dry_run: bool) -> tuple[int, int, int]:
    """Handle backfill collection.

    Args:
        col: Value for ``col``.
        key_field (str): Value for ``key_field``.
        dry_run (bool): Value for ``dry_run``.

    Returns:
        tuple[int, int, int]: The function result.
    """
    scanned = 0
    updated = 0
    failed = 0
    projection = {"_id": 1, key_field: 1, "username": 1, "email": 1, "name": 1}
    for doc in col.find({}, projection):
        scanned += 1
        target = _resolve_business_key(doc, key_field)
        if not target:
            continue
        current = _normalize(doc.get(key_field), lowercase=(key_field == "role_id"))
        if current == target:
            continue
        if dry_run:
            updated += 1
            continue
        try:
            result = col.update_one({"_id": doc.get("_id")}, {"$set": {key_field: target}})
            if result.modified_count:
                updated += 1
        except PyMongoError:
            failed += 1
    return scanned, updated, failed


def ensure_index(col, key_field: str, dry_run: bool) -> str:
    """Handle ensure index.

    Args:
        col: Value for ``col``.
        key_field (str): Value for ``key_field``.
        dry_run (bool): Value for ``dry_run``.

    Returns:
        str: The function result.
    """
    index_name = f"{key_field}_1"
    if dry_run:
        return index_name
    try:
        col.create_index(
            [(key_field, 1)],
            name=index_name,
            unique=True,
            background=True,
            partialFilterExpression={key_field: {"$exists": True, "$type": "string"}},
        )
    except OperationFailure as exc:
        if getattr(exc, "code", None) != 85:
            raise
    return index_name


def main() -> int:
    """Handle main.

    Returns:
        int: The function result.
    """
    args = parse_args()
    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=7000)
    try:
        client.admin.command("ping")
    except PyMongoError as exc:
        print(f"[error] Mongo connection failed: {exc}")
        return 2

    total_failed = 0
    for db_name in args.dbs:
        db = client[db_name]
        print(f"\n[db] {db_name}")
        existing = set(db.list_collection_names())
        for rule in RULES:
            target_cols = [c for c in rule.collection_names if c in existing]
            if not target_cols:
                print(f"[skip] {rule.collection_names[0]} missing")
                continue
            for target_col in target_cols:
                col = db[target_col]
                scanned, updated, failed = backfill_collection(col, rule.key_field, args.dry_run)
                index_name = ensure_index(col, rule.key_field, args.dry_run)
                total_failed += failed
                print(
                    f"[ok] {target_col}: key={rule.key_field} scanned={scanned} updated={updated} "
                    f"failed={failed} index={index_name} dry_run={args.dry_run}"
                )

    print(f"\n[done] total_failed={total_failed}")
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
