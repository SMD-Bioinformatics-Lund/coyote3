#!/usr/bin/env python3
"""Canonical DB migration script for identity fields and variant identity hashes.

This script performs:
1) Non-ObjectId `_id` migration:
   - convert docs to ObjectId `_id`
   - copy previous `_id` value into a business key field
   - ensure unique index on that business key
2) Explicit business-key normalization for core admin collections:
   - users.username
   - roles.role_id
   - permissions.permission_id
   - schemas.schema_id
3) samples.name unique index enforcement
4) variants simple_id/simple_id_hash backfill + identity index enforcement

It is idempotent and supports dry-run.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from bson import ObjectId
from pymongo import MongoClient, UpdateOne
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, OperationFailure, PyMongoError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def ensure_variant_identity_fields(doc: dict[str, Any]) -> dict[str, Any]:
    """Lazy-import variant identity normalizer after project path bootstrap."""
    from api.core.dna.variant_identity import (
        ensure_variant_identity_fields as _ensure_variant_identity_fields,
    )

    return _ensure_variant_identity_fields(doc)


@dataclass
class Counters:
    scanned: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    failed: int = 0


EXPLICIT_KEY_RULES: tuple[tuple[str, str], ...] = (
    ("users", "username"),
    ("roles", "role_id"),
    ("permissions", "permission_id"),
    ("schemas", "schema_id"),
    ("asp_configs", "aspc_id"),
    ("assay_specific_panels", "asp_id"),
    ("hgnc_genes", "hgnc_id"),
    ("insilico_genelists", "isgl_id"),
    ("vep_metadata", "vep_id"),
)

EXPLICIT_KEY_FIELDS = {collection: key_field for collection, key_field in EXPLICIT_KEY_RULES}

# Legacy collection names that should be normalized to canonical names.
LEGACY_COLLECTION_ALIASES: tuple[tuple[str, str], ...] = (("transloc", "translocations"),)

# By default scan all non-system collections with non-ObjectId `_id`.
DEFAULT_EXCLUDED_STRING_ID_COLLECTIONS: set[str] = set()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Canonical Coyote3 DB identity migration.")
    parser.add_argument("--mongo-uri", default="mongodb://localhost:27017")
    parser.add_argument(
        "--db", action="append", dest="dbs", required=True, help="Target DB; repeatable"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--fill-fullname", action="store_true", help="Fill users.fullname from username if missing"
    )
    parser.add_argument(
        "--default-role", default="", help="Default role to set on users when missing"
    )
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument(
        "--explicit-only",
        action="store_true",
        help="Run only explicit core rules instead of scanning all collections.",
    )
    parser.add_argument(
        "--exclude-collection",
        action="append",
        default=[],
        help="Collection name to exclude from generic non-ObjectId `_id` migration. Repeatable.",
    )
    parser.add_argument(
        "--include-collection",
        action="append",
        default=[],
        help="Collection name to force-include for generic non-ObjectId `_id` migration. Repeatable.",
    )
    return parser.parse_args()


def _norm(value: Any, *, lowercase: bool = False) -> str | None:
    if value is None:
        return None
    out = str(value).strip()
    if lowercase:
        out = out.lower()
    return out or None


def _normalize_key_value(key_field: str, value: str | None) -> str | None:
    """Normalize business-key values consistently where required."""
    if value is None:
        return None
    if key_field in {"username", "role_id"}:
        return value.lower()
    return value


def _resolve_business_key(doc: dict[str, Any], key_field: str) -> str | None:
    lower = key_field in {"username", "role_id"}
    current = _norm(doc.get(key_field), lowercase=lower)
    if current:
        return current
    for src in ("username", "email", "name", "_id"):
        candidate = _norm(doc.get(src), lowercase=lower)
        if candidate:
            return candidate
    return None


def _id_key_builder(collection_name: str, key_field: str) -> Callable[[dict[str, Any]], str | None]:
    """Return key builder for non-ObjectId `_id` migration."""
    if collection_name == "hgnc_genes":
        # Preserve existing HGNC business key when present; only fallback to old _id.
        return lambda doc: _normalize_key_value(
            key_field,
            _norm(doc.get(key_field)) or _norm(doc.get("_id")),
        )
    return lambda doc: _normalize_key_value(key_field, _norm(doc.get("_id")))


def _key_field_for_collection(collection_name: str) -> str:
    """Derive the business-key field for generic id migration."""
    explicit = EXPLICIT_KEY_FIELDS.get(collection_name)
    if explicit:
        return explicit

    name = collection_name.strip().lower()
    if name.endswith("ies"):
        stem = name[:-3] + "y"
    elif name.endswith("ses"):
        stem = name[:-2]
    elif name.endswith("s"):
        stem = name[:-1]
    else:
        stem = name
    return f"{stem}_id"


def ensure_unique_partial_string_index(col: Collection, field: str, dry_run: bool) -> str:
    index_name = f"{field}_1"
    if dry_run:
        return index_name
    desired = {field: {"$exists": True, "$type": "string"}}
    try:
        col.create_index(
            [(field, 1)],
            name=index_name,
            unique=True,
            background=True,
            partialFilterExpression=desired,
        )
    except OperationFailure as exc:
        if getattr(exc, "code", None) not in {85, 86}:
            raise
        existing = col.index_information().get(index_name, {})
        is_desired = (
            existing.get("key") == [(field, 1)]
            and bool(existing.get("unique"))
            and existing.get("partialFilterExpression") == desired
        )
        if not is_desired:
            col.drop_index(index_name)
            col.create_index(
                [(field, 1)],
                name=index_name,
                unique=True,
                background=True,
                partialFilterExpression=desired,
            )
    return index_name


def ensure_samples_name_index(db, dry_run: bool) -> str | None:
    if "samples" not in set(db.list_collection_names()):
        return None
    return ensure_unique_partial_string_index(db["samples"], "name", dry_run)


def normalize_users_collection(
    col: Collection, *, dry_run: bool, fill_fullname: bool, default_role: str | None
) -> Counters:
    counters = Counters()
    projection = {
        "_id": 1,
        "username": 1,
        "email": 1,
        "fullname": 1,
        "role": 1,
        "is_active": 1,
    }
    for doc in col.find({}, projection):
        counters.scanned += 1
        updates: dict[str, Any] = {}

        resolved = _resolve_business_key(doc, "username")
        if not resolved:
            counters.skipped += 1
            continue

        username = _norm(doc.get("username"), lowercase=True) or resolved
        if _norm(doc.get("username"), lowercase=True) != username:
            updates["username"] = username

        email = _norm(doc.get("email"), lowercase=True)
        if email and doc.get("email") != email:
            updates["email"] = email

        if "is_active" not in doc:
            updates["is_active"] = True

        if fill_fullname and not _norm(doc.get("fullname")) and username:
            updates["fullname"] = username

        role_default = _norm(default_role)
        if role_default and not _norm(doc.get("role")):
            updates["role"] = role_default

        if "user_id" in doc:
            updates["user_id"] = None

        if not updates:
            counters.unchanged += 1
            continue
        if dry_run:
            counters.updated += 1
            continue
        try:
            set_updates = {k: v for k, v in updates.items() if v is not None}
            unset_updates = {k: "" for k, v in updates.items() if v is None}
            update_doc: dict[str, Any] = {}
            if set_updates:
                update_doc["$set"] = set_updates
            if unset_updates:
                update_doc["$unset"] = unset_updates
            res = col.update_one({"_id": doc.get("_id")}, update_doc)
            if res.modified_count:
                counters.updated += 1
            else:
                counters.unchanged += 1
        except (DuplicateKeyError, PyMongoError):
            counters.failed += 1
    return counters


def migrate_non_objectid_ids(
    col: Collection,
    key_field: str,
    dry_run: bool,
    *,
    key_value_builder: Callable[[dict[str, Any]], str | None] | None = None,
) -> Counters:
    """Convert non-ObjectId `_id` docs to ObjectId while preserving old `_id` in key_field."""
    counters = Counters()
    projection = {"_id": 1, key_field: 1, "username": 1, "email": 1, "name": 1}

    for doc in col.find({}, projection):
        counters.scanned += 1
        old_id = doc.get("_id")
        if isinstance(old_id, ObjectId):
            counters.unchanged += 1
            continue

        if key_value_builder is not None:
            business_key = key_value_builder(doc)
        else:
            business_key = _norm(old_id)
        business_key = _normalize_key_value(key_field, business_key)

        if not business_key:
            counters.skipped += 1
            continue
        if dry_run:
            counters.updated += 1
            continue

        try:
            canonical = col.find_one({key_field: business_key})
            if canonical and isinstance(canonical.get("_id"), ObjectId):
                col.delete_one({"_id": old_id})
                counters.updated += 1
                continue

            full_doc = col.find_one({"_id": old_id})
            if not full_doc:
                counters.skipped += 1
                continue

            col.update_one({"_id": old_id}, {"$unset": {key_field: ""}})
            full_doc.pop("_id", None)
            full_doc[key_field] = business_key
            col.insert_one(full_doc)
            col.delete_one({"_id": old_id})
            counters.updated += 1
        except PyMongoError:
            counters.failed += 1

    return counters


def backfill_business_key(col: Collection, key_field: str, dry_run: bool) -> Counters:
    counters = Counters()
    projection = {"_id": 1, key_field: 1, "username": 1, "email": 1, "name": 1}
    for doc in col.find({}, projection):
        counters.scanned += 1
        target = _resolve_business_key(doc, key_field)
        if not target:
            counters.skipped += 1
            continue
        current = _norm(doc.get(key_field), lowercase=(key_field in {"username", "role_id"}))
        if current == target:
            counters.unchanged += 1
            continue
        if dry_run:
            counters.updated += 1
            continue
        try:
            res = col.update_one({"_id": doc.get("_id")}, {"$set": {key_field: target}})
            if res.modified_count:
                counters.updated += 1
            else:
                counters.unchanged += 1
        except PyMongoError:
            counters.failed += 1
    return counters


def ensure_variants_identity_index(db, dry_run: bool) -> str | None:
    if "variants" not in set(db.list_collection_names()):
        return None
    if dry_run:
        return "simple_id_hash_1_simple_id_1"
    db["variants"].create_index(
        [("simple_id_hash", 1), ("simple_id", 1)],
        name="simple_id_hash_1_simple_id_1",
        background=True,
        partialFilterExpression={
            "simple_id_hash": {"$exists": True, "$type": "string"},
            "simple_id": {"$exists": True, "$type": "string"},
        },
    )
    return "simple_id_hash_1_simple_id_1"


def cleanup_legacy_variant_simple_id_indexes(db, dry_run: bool) -> list[str]:
    """Drop legacy variants indexes that rely on `simple_id` without hash prefilter.

    This keeps identity lookups hash-first (`simple_id_hash` + `simple_id`) and
    avoids carrying oversized simple_id-only index structures.
    """
    if "variants" not in set(db.list_collection_names()):
        return []

    col = db["variants"]
    dropped: list[str] = []
    keep_names = {
        "_id_",
        "simple_id_hash_1_simple_id_1",
        "fp_1_simple_id_hash_1_simple_id_1",
    }
    for idx in col.list_indexes():
        name = str(idx.get("name") or "")
        if not name or name in keep_names:
            continue
        key_doc = idx.get("key") or {}
        key_fields = list(dict(key_doc).keys())
        has_simple_id = "simple_id" in key_fields
        has_hash = "simple_id_hash" in key_fields
        if has_simple_id and not has_hash:
            dropped.append(name)
            if not dry_run:
                col.drop_index(name)
    return dropped


def backfill_variant_identity(db, *, batch_size: int, dry_run: bool) -> Counters:
    counters = Counters()
    if "variants" not in set(db.list_collection_names()):
        counters.skipped = 1
        return counters

    col = db["variants"]
    ops: list[UpdateOne] = []
    projection = {
        "_id": 1,
        "simple_id": 1,
        "simple_id_hash": 1,
        "CHROM": 1,
        "POS": 1,
        "REF": 1,
        "ALT": 1,
    }

    for doc in col.find({}, projection):
        counters.scanned += 1
        normalized = ensure_variant_identity_fields(doc)
        target_simple = normalized.get("simple_id")
        target_hash = normalized.get("simple_id_hash")

        if doc.get("simple_id") == target_simple and doc.get("simple_id_hash") == target_hash:
            counters.unchanged += 1
            continue

        if dry_run:
            counters.updated += 1
            continue

        ops.append(
            UpdateOne(
                {"_id": doc["_id"]},
                {"$set": {"simple_id": target_simple, "simple_id_hash": target_hash}},
            )
        )

        if len(ops) >= batch_size:
            try:
                result = col.bulk_write(ops, ordered=False)
                counters.updated += int(result.modified_count or 0)
            except PyMongoError:
                counters.failed += len(ops)
            finally:
                ops = []

    if ops:
        try:
            result = col.bulk_write(ops, ordered=False)
            counters.updated += int(result.modified_count or 0)
        except PyMongoError:
            counters.failed += len(ops)

    return counters


def _has_non_objectid_ids(col: Collection) -> bool:
    probe = col.find_one({"_id": {"$not": {"$type": "objectId"}}}, {"_id": 1})
    return bool(probe)


def _resolve_migration_rules(
    db,
    *,
    migrate_all_collections: bool,
    excludes: set[str],
    includes: set[str],
) -> list[tuple[str, str]]:
    existing = set(db.list_collection_names())
    rules: list[tuple[str, str]] = []
    explicit_names = set()

    for collection_name, key_field in EXPLICIT_KEY_RULES:
        if collection_name in existing:
            rules.append((collection_name, key_field))
            explicit_names.add(collection_name)

    if not migrate_all_collections:
        return rules

    for collection_name in sorted(existing):
        if collection_name.startswith("system."):
            continue
        if collection_name in explicit_names:
            continue
        if collection_name in excludes and collection_name not in includes:
            continue
        col = db[collection_name]
        if collection_name in includes or _has_non_objectid_ids(col):
            rules.append((collection_name, _key_field_for_collection(collection_name)))
    return rules


def normalize_collection_aliases(db, *, dry_run: bool) -> int:
    """Normalize legacy collection aliases to canonical collection names.

    Returns:
        Number of failures encountered.
    """
    failed = 0
    existing = set(db.list_collection_names())
    for legacy_name, canonical_name in LEGACY_COLLECTION_ALIASES:
        if legacy_name not in existing:
            continue
        legacy = db[legacy_name]
        legacy_count = legacy.count_documents({})

        if canonical_name not in existing:
            print(
                f"[alias] {legacy_name} -> {canonical_name}: "
                f"mode={'rename' if not dry_run else 'rename-plan'} count={legacy_count}"
            )
            if not dry_run:
                try:
                    legacy.rename(canonical_name)
                except PyMongoError as exc:
                    failed += 1
                    print(f"[error] alias rename failed {legacy_name}->{canonical_name}: {exc}")
            continue

        canonical = db[canonical_name]
        canonical_count = canonical.count_documents({})
        print(
            f"[alias] {legacy_name} -> {canonical_name}: "
            f"both-exist legacy_count={legacy_count} canonical_count={canonical_count}"
        )
        if legacy_count == 0:
            if not dry_run:
                try:
                    legacy.drop()
                    print(f"[alias] dropped empty legacy collection: {legacy_name}")
                except PyMongoError as exc:
                    failed += 1
                    print(f"[error] failed to drop empty legacy collection {legacy_name}: {exc}")
            continue
        if canonical_count == 0:
            print(
                f"[alias] {legacy_name} -> {canonical_name}: "
                f"canonical empty, mode={'rename' if not dry_run else 'rename-plan'}"
            )
            if not dry_run:
                try:
                    legacy.rename(canonical_name, dropTarget=True)
                except PyMongoError as exc:
                    failed += 1
                    print(
                        f"[error] alias rename with dropTarget failed {legacy_name}->{canonical_name}: {exc}"
                    )
            continue
        print(
            f"[warn] alias not auto-merged for {legacy_name}->{canonical_name}; "
            "both collections contain data"
        )
    return failed


def run_for_db(db, args: argparse.Namespace) -> int:
    failed = 0
    print(f"\n[db] {db.name}")

    failed += normalize_collection_aliases(db, dry_run=args.dry_run)

    name_index = ensure_samples_name_index(db, args.dry_run)
    if name_index:
        print(f"[samples] unique index ensured: {name_index} dry_run={args.dry_run}")

    excludes = set(DEFAULT_EXCLUDED_STRING_ID_COLLECTIONS) | set(args.exclude_collection or [])
    includes = set(args.include_collection or [])
    rules = _resolve_migration_rules(
        db,
        migrate_all_collections=not bool(args.explicit_only),
        excludes=excludes,
        includes=includes,
    )
    print(
        "[plan] id-migration rules: "
        + ", ".join(f"{collection}.{key}" for collection, key in rules)
    )

    for collection_name, key_field in rules:
        col = db[collection_name]
        id_migrate = migrate_non_objectid_ids(
            col,
            key_field,
            args.dry_run,
            key_value_builder=_id_key_builder(collection_name, key_field),
        )
        print(
            f"[ids] {collection_name}: key={key_field} scanned={id_migrate.scanned} "
            f"updated={id_migrate.updated} unchanged={id_migrate.unchanged} "
            f"skipped={id_migrate.skipped} failed={id_migrate.failed} dry_run={args.dry_run}"
        )
        failed += id_migrate.failed

        if collection_name == "users":
            users_norm = normalize_users_collection(
                col,
                dry_run=args.dry_run,
                fill_fullname=args.fill_fullname,
                default_role=args.default_role or None,
            )
            print(
                f"[users] scanned={users_norm.scanned} updated={users_norm.updated} "
                f"unchanged={users_norm.unchanged} skipped={users_norm.skipped} failed={users_norm.failed}"
            )
            failed += users_norm.failed
            email_idx = ensure_unique_partial_string_index(col, "email", args.dry_run)
            print(f"[index] {collection_name}: key=email index={email_idx} dry_run={args.dry_run}")

        if collection_name in EXPLICIT_KEY_FIELDS:
            key_backfill = backfill_business_key(col, key_field, args.dry_run)
            print(
                f"[keys] {collection_name}: key={key_field} scanned={key_backfill.scanned} "
                f"updated={key_backfill.updated} unchanged={key_backfill.unchanged} "
                f"skipped={key_backfill.skipped} failed={key_backfill.failed} dry_run={args.dry_run}"
            )
            failed += key_backfill.failed

        idx = ensure_unique_partial_string_index(col, key_field, args.dry_run)
        print(f"[index] {collection_name}: key={key_field} index={idx} dry_run={args.dry_run}")

    variant_idx = ensure_variants_identity_index(db, args.dry_run)
    if variant_idx:
        print(f"[variants] identity index ensured: {variant_idx} dry_run={args.dry_run}")
    dropped_legacy_variant_indexes = cleanup_legacy_variant_simple_id_indexes(db, args.dry_run)
    if dropped_legacy_variant_indexes:
        print(
            "[variants] dropped legacy simple_id indexes: "
            + ", ".join(dropped_legacy_variant_indexes)
            + f" dry_run={args.dry_run}"
        )
    else:
        print(f"[variants] no legacy simple_id-only indexes found dry_run={args.dry_run}")

    variant_counts = backfill_variant_identity(db, batch_size=args.batch_size, dry_run=args.dry_run)
    print(
        f"[variants] scanned={variant_counts.scanned} updated={variant_counts.updated} "
        f"unchanged={variant_counts.unchanged} skipped={variant_counts.skipped} failed={variant_counts.failed} "
        f"dry_run={args.dry_run}"
    )
    failed += variant_counts.failed

    return failed


def main() -> int:
    args = parse_args()
    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=7000)
    try:
        client.admin.command("ping")
    except PyMongoError as exc:
        print(f"[error] Mongo connection failed: {exc}")
        return 2

    total_failed = 0
    for db_name in args.dbs:
        total_failed += run_for_db(client[db_name], args)

    print(f"\n[summary] total_failed={total_failed}")
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
