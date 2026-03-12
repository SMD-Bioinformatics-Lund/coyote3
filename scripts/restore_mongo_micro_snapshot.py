#!/usr/bin/env python3
"""
Restore a tiny Mongo snapshot created by create_mongo_micro_snapshot.py.

This script restores docs and indexes directly via PyMongo, so it works
for Docker Mongo containers exposed on a URI without requiring mongoimport.
"""

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib  # py312
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from bson import json_util
from pymongo import MongoClient
from pymongo.errors import OperationFailure, PyMongoError


"""
/home/ram/.virtualenvs/coyote3/bin/python scripts/restore_mongo_micro_snapshot.py \
  --snapshot-dir var/mongo/micro_snapshot \
  --target dev \
  --drop-db \
  --db-map coyote3=coyote_dev_3
"""


DEFAULT_COLLECTIONS_TOML = Path("config/coyote3_collections.toml")


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
    parser = argparse.ArgumentParser(description="Restore Coyote3 Mongo micro snapshot.")
    parser.add_argument(
        "--mongo-uri",
        default=os.getenv("COYOTE3_RESTORE_MONGO_URI", "mongodb://localhost:37017"),
        help="Mongo URI to restore into (default: env COYOTE3_RESTORE_MONGO_URI or mongodb://localhost:37017)",
    )
    parser.add_argument(
        "--snapshot-dir",
        default="var/mongo/micro_snapshot",
        help="Snapshot directory containing manifest.json",
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop target collections before restore",
    )
    parser.add_argument(
        "--drop-db",
        action="store_true",
        help="Drop each target database before restoring collections",
    )
    parser.add_argument(
        "--target",
        choices=("dev", "portable", "custom"),
        default="dev",
        help="Restore target preset (default: dev)",
    )
    parser.add_argument(
        "--db-map",
        action="append",
        default=[],
        help="Map source DB to target DB, e.g. --db-map coyote3=coyote_dev_3",
    )
    parser.add_argument(
        "--collections-toml",
        default=str(DEFAULT_COLLECTIONS_TOML),
        help=f"Path to collections TOML for collection-name remapping (default: {DEFAULT_COLLECTIONS_TOML})",
    )
    return parser.parse_args()


def read_ndjson(path: Path) -> list[dict[str, Any]]:
    """Handle read ndjson.

    Args:
        path (Path): Value for ``path``.

    Returns:
        list[dict[str, Any]]: The function result.
    """
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json_util.loads(line))
    return rows


def _normalize_index_direction(value: Any) -> Any:
    """Handle  normalize index direction.

    Args:
            value: Value.

    Returns:
            The  normalize index direction result.
    """
    if isinstance(value, dict):
        if "$numberInt" in value:
            return int(value["$numberInt"])
        if "$numberLong" in value:
            return int(value["$numberLong"])
        if "$numberDouble" in value:
            as_float = float(value["$numberDouble"])
            return int(as_float) if as_float.is_integer() else as_float
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _normalize_index_keys(key_doc: dict[str, Any]) -> list[tuple[str, Any]]:
    """Handle  normalize index keys.

    Args:
            key_doc: Key doc.

    Returns:
            The  normalize index keys result.
    """
    key_items: list[tuple[str, Any]] = []
    for field, direction in (key_doc or {}).items():
        key_items.append((field, _normalize_index_direction(direction)))
    return key_items


def restore_indexes(coll, index_rows: list[dict[str, Any]]) -> None:
    """Handle restore indexes.

    Args:
        coll: Value for ``coll``.
        index_rows (list[dict[str, Any]]): Value for ``index_rows``.

    Returns:
        None.
    """
    for idx in index_rows:
        if idx.get("name") == "_id_":
            continue
        key_doc = idx.get("key") or {}
        key_items = _normalize_index_keys(key_doc)
        options = {}
        for opt in ("name", "unique", "sparse", "expireAfterSeconds", "partialFilterExpression", "collation"):
            if opt in idx:
                options[opt] = idx[opt]
        try:
            coll.create_index(key_items, **options)
        except Exception as exc:
            print(
                f"[warn] skipped index on {coll.full_name}: "
                f"name={idx.get('name')} keys={key_items} reason={exc}"
            )


def resolve_mongo_uri(args: argparse.Namespace) -> str:
    """Handle resolve mongo uri.

    Args:
        args (argparse.Namespace): Value for ``args``.

    Returns:
        str: The function result.
    """
    if args.target == "portable":
        return os.getenv("COYOTE3_PORTABLE_RESTORE_MONGO_URI", "mongodb://localhost:47017")
    if args.target == "custom":
        return str(args.mongo_uri)
    return str(args.mongo_uri)


def load_collections_map(path: Path) -> dict[str, dict[str, str]]:
    """Load collections map.

    Args:
        path (Path): Value for ``path``.

    Returns:
        dict[str, dict[str, str]]: The function result.
    """
    if not path.exists():
        raise FileNotFoundError(f"Collections config not found: {path}")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict[str, str]] = {}
    for db_name, mapping in data.items():
        if isinstance(mapping, dict):
            out[str(db_name)] = {
                str(alias): str(coll_name)
                for alias, coll_name in mapping.items()
                if str(alias).strip() and str(coll_name).strip()
            }
    return out


def parse_db_map(rows: list[str]) -> dict[str, str]:
    """Handle parse db map.

    Args:
        rows (list[str]): Value for ``rows``.

    Returns:
        dict[str, str]: The function result.
    """
    mapping: dict[str, str] = {}
    for row in rows or []:
        if "=" not in str(row):
            raise ValueError(f"Invalid --db-map entry: {row!r}")
        source, target = str(row).split("=", 1)
        source = source.strip()
        target = target.strip()
        if not source or not target:
            raise ValueError(f"Invalid --db-map entry: {row!r}")
        mapping[source] = target
    return mapping


def reverse_collection_map(mapping: dict[str, str]) -> dict[str, str]:
    """Handle reverse collection map.

    Args:
        mapping (dict[str, str]): Value for ``mapping``.

    Returns:
        dict[str, str]: The function result.
    """
    return {collection: alias for alias, collection in mapping.items()}


def resolve_target_collection_name(
    *,
    source_db: str,
    source_collection: str,
    target_db: str,
    collections_by_db: dict[str, dict[str, str]],
) -> str:
    """Handle resolve target collection name.

    Args:
        source_db (str): Value for ``source_db``.
        source_collection (str): Value for ``source_collection``.
        target_db (str): Value for ``target_db``.
        collections_by_db (dict[str, dict[str, str]]): Value for ``collections_by_db``.

    Returns:
        str: The function result.
    """
    if source_db == target_db:
        return source_collection

    source_mapping = collections_by_db.get(source_db) or {}
    target_mapping = collections_by_db.get(target_db) or {}
    source_reverse = reverse_collection_map(source_mapping)
    alias = source_reverse.get(source_collection)
    if alias and alias in target_mapping:
        return target_mapping[alias]
    return source_collection


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
    for src in ("_id", "username", "email", "name", "permission_name", "schema_name", "assay_name"):
        candidate = _normalize(doc.get(src), lowercase=lower)
        if candidate:
            return candidate
    return None


def _backfill_collection_keys(col, key_field: str) -> tuple[int, int, int]:
    """Handle  backfill collection keys.

    Args:
            col: Col.
            key_field: Key field.

    Returns:
            The  backfill collection keys result.
    """
    scanned = 0
    updated = 0
    failed = 0
    projection = {
        "_id": 1,
        key_field: 1,
        "username": 1,
        "email": 1,
        "name": 1,
        "permission_name": 1,
        "schema_name": 1,
        "assay_name": 1,
    }
    for doc in col.find({}, projection):
        scanned += 1
        target = _resolve_business_key(doc, key_field)
        if not target:
            continue
        current = _normalize(doc.get(key_field), lowercase=(key_field == "role_id"))
        if current == target:
            continue
        try:
            result = col.update_one({"_id": doc.get("_id")}, {"$set": {key_field: target}})
            if result.modified_count:
                updated += 1
        except PyMongoError:
            failed += 1
    return scanned, updated, failed


def _ensure_business_key_index(col, key_field: str) -> str:
    """Handle  ensure business key index.

    Args:
            col: Col.
            key_field: Key field.

    Returns:
            The  ensure business key index result.
    """
    index_name = f"{key_field}_1"
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


def backfill_business_keys_for_db(db) -> None:
    """Handle backfill business keys for db.

    Args:
        db: Value for ``db``.

    Returns:
        None.
    """
    existing = set(db.list_collection_names())
    for rule in RULES:
        target_cols = [c for c in rule.collection_names if c in existing]
        for target_col in target_cols:
            col = db[target_col]
            scanned, updated, failed = _backfill_collection_keys(col, rule.key_field)
            index_name = _ensure_business_key_index(col, rule.key_field)
            print(
                f"[ok] backfilled {db.name}.{target_col}: key={rule.key_field} "
                f"scanned={scanned} updated={updated} failed={failed} index={index_name}"
            )


def main() -> int:
    """Handle main.

    Returns:
        int: The function result.
    """
    args = parse_args()
    mongo_uri = resolve_mongo_uri(args)
    root = Path(args.snapshot_dir)
    manifest_file = root / "manifest.json"
    if not manifest_file.exists():
        print(f"[error] manifest not found: {manifest_file}")
        return 2

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    dbs = manifest.get("dbs") or {}
    if not isinstance(dbs, dict) or not dbs:
        print("[error] invalid or empty snapshot manifest")
        return 3

    try:
        db_map = parse_db_map(args.db_map)
        collections_by_db = load_collections_map(Path(args.collections_toml))
    except Exception as exc:
        print(f"[error] restore configuration failed: {exc}")
        return 3

    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=7000)
        client.admin.command("ping")
    except PyMongoError as exc:
        print(f"[error] Mongo connection failed: {exc}")
        return 4

    dropped_dbs: set[str] = set()
    touched_target_dbs: set[str] = set()
    for source_db_name, collections in dbs.items():
        target_db_name = db_map.get(source_db_name, source_db_name)
        db = client[target_db_name]
        touched_target_dbs.add(target_db_name)
        if args.drop_db:
            if target_db_name not in dropped_dbs:
                client.drop_database(target_db_name)
                dropped_dbs.add(target_db_name)
                db = client[target_db_name]
                print(f"[ok] dropped database {target_db_name}")
        for source_coll_name, meta in (collections or {}).items():
            target_coll_name = resolve_target_collection_name(
                source_db=source_db_name,
                source_collection=source_coll_name,
                target_db=target_db_name,
                collections_by_db=collections_by_db,
            )
            coll = db[target_coll_name]
            docs_file = root / meta["docs_file"]
            idx_file = root / meta["indexes_file"]
            docs = read_ndjson(docs_file)
            indexes = read_ndjson(idx_file)

            if args.drop:
                coll.drop()
                coll = db[target_coll_name]

            if docs:
                coll.insert_many(docs, ordered=False)
            restore_indexes(coll, indexes)
            print(
                f"[ok] restored {source_db_name}.{source_coll_name} "
                f"-> {target_db_name}.{target_coll_name}: {len(docs)} docs"
            )

    for target_db_name in sorted(touched_target_dbs):
        backfill_business_keys_for_db(client[target_db_name])

    print("[done] restore complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
