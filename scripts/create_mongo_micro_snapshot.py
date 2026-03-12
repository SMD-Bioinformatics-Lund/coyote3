#!/usr/bin/env python3
"""
Create a tiny Mongo snapshot for all configured Coyote3 collections.

Output format:
  <out_dir>/
    manifest.json
    <db_name>/<collection>.ndjson
    <db_name>/<collection>.indexes.ndjson

Sample-driven export behavior:
  - Select latest N sample docs per assay from the "samples" collection (--sample-limit).
  - For any other collection that contains SAMPLE_ID, export all docs for selected sample IDs.
  - For collections without SAMPLE_ID, export full data.

This is designed for local/dev bootstrap in Docker Mongo with realistic sample-linked data.
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import tomllib  # py312
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from bson import json_util
from pymongo import MongoClient
from pymongo.errors import PyMongoError

"""
python scripts/create_mongo_micro_snapshot.py --mongo-uri "mongodb://172.17.0.1:27017" --db coyote3 --db BAM_Service --out .internal/mongo_micro_snapshot
"""




DEFAULT_COLLECTIONS_TOML = Path("config/coyote3_collections.toml")


@dataclass(frozen=True)
class SnapshotConfig:
    mongo_uri: str
    db_names: List[str]
    collections_toml: Path
    out_dir: Path
    sample_limit: int
    full_collections: set


def parse_args() -> SnapshotConfig:
    parser = argparse.ArgumentParser(description="Create tiny Mongo snapshot for Coyote3 collections.")
    parser.add_argument(
        "--mongo-uri",
        default=os.getenv("MONGO_URI") or os.getenv("COYOTE3_MONGO_URI") or "mongodb://localhost:27017",
        help="Mongo URI (default: env MONGO_URI/COYOTE3_MONGO_URI or mongodb://localhost:27017)",
    )
    parser.add_argument(
        "--db",
        action="append",
        dest="dbs",
        help="DB name to include (can be set multiple times). Defaults to COYOTE3_DB_NAME and BAM_DB.",
    )
    parser.add_argument(
        "--collections-toml",
        default=str(DEFAULT_COLLECTIONS_TOML),
        help=f"Path to collections TOML (default: {DEFAULT_COLLECTIONS_TOML})",
    )
    parser.add_argument(
        "--out",
        default=".internal/mongo_micro_snapshot",
        help="Output directory (default: .internal/mongo_micro_snapshot)",
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=10,
        help="Number of latest sample docs to include per assay from samples collection (default: 10)",
    )
    parser.add_argument(
        "--full-collection",
        action="append",
        dest="full_collections",
        default=[],
        help=(
            "Collection name to export fully (no limit). Can be passed multiple times, "
            "e.g. --full-collection users --full-collection annotation"
        ),
    )

    args = parser.parse_args()
    db_names = args.dbs or [
        os.getenv("COYOTE3_DB_NAME", "coyote3"),
        os.getenv("BAM_DB", "BAM_Service"),
    ]
    db_names = [str(x).strip() for x in db_names if str(x).strip()]
    return SnapshotConfig(
        mongo_uri=str(args.mongo_uri),
        db_names=db_names,
        collections_toml=Path(args.collections_toml),
        out_dir=Path(args.out),
        sample_limit=max(1, int(args.sample_limit)),
        full_collections={str(x).strip() for x in (args.full_collections or []) if str(x).strip()},
    )


def load_collections_map(path: Path) -> Dict[str, List[str]]:
    if not path.exists():
        raise FileNotFoundError(f"Collections config not found: {path}")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    out: Dict[str, List[str]] = {}
    for db_name, mapping in data.items():
        if isinstance(mapping, dict):
            coll_names = sorted({str(v).strip() for v in mapping.values() if str(v).strip()})
            out[str(db_name)] = coll_names
    return out


def write_ndjson(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json_util.dumps(row, json_options=json_util.CANONICAL_JSON_OPTIONS))
            fh.write("\n")


def sanitize_uri(uri: str) -> str:
    # Minimal sanitization for manifest readability.
    if "@" not in uri:
        return uri
    left, right = uri.split("@", 1)
    proto = left.split("://", 1)[0] if "://" in left else "mongodb"
    return f"{proto}://***:***@{right}"


def pick_sample_collection(collections: List[str]) -> Optional[str]:
    if "samples" in collections:
        return "samples"
    candidates = [c for c in collections if "sample" in c.lower()]
    return sorted(candidates)[0] if candidates else None


def choose_sample_sort(coll) -> List[Tuple[str, int]]:
    candidates = ("time_added", "TIME_ADDED", "updated_at", "created_at", "timestamp", "DATE")
    for field in candidates:
        try:
            if coll.find_one({field: {"$exists": True}}, {"_id": 1}) is not None:
                return [(field, -1), ("_id", -1)]
        except Exception:
            continue
    return [("_id", -1)]


def get_sample_assays(coll) -> List[Any]:
    try:
        values = list(coll.distinct("assay", {"assay": {"$exists": True, "$ne": None}}))
    except Exception:
        values = []
    return sorted((value for value in values if value not in ("", None)), key=lambda value: str(value).lower())


def select_latest_samples_per_assay(coll, sample_limit: int) -> Tuple[List[Dict[str, Any]], int]:
    sample_sort = choose_sample_sort(coll)
    assay_values = get_sample_assays(coll)
    selected_samples: List[Dict[str, Any]] = []

    if not assay_values:
        try:
            selected_samples = list(coll.find({}, sort=sample_sort, limit=sample_limit))
        except Exception:
            selected_samples = list(coll.find({}).sort(sample_sort).limit(sample_limit))
        unique_sample_ids = {
            str(doc.get("_id")) for doc in selected_samples if doc.get("_id") is not None
        }
        return selected_samples, len(unique_sample_ids)

    for assay in assay_values:
        query = {"assay": assay}
        try:
            docs = list(coll.find(query, sort=sample_sort, limit=sample_limit))
        except Exception:
            docs = list(coll.find(query).sort(sample_sort).limit(sample_limit))
        selected_samples.extend(docs)

    unique_sample_ids = {
        str(doc.get("_id")) for doc in selected_samples if doc.get("_id") is not None
    }
    return selected_samples, len(unique_sample_ids)


def has_sample_id_field(coll) -> bool:
    try:
        return coll.find_one({"SAMPLE_ID": {"$exists": True}}, {"_id": 1}) is not None
    except Exception:
        return False


def main() -> int:
    cfg = parse_args()
    collections_by_db = load_collections_map(cfg.collections_toml)
    requested_dbs = [db for db in cfg.db_names if db in collections_by_db]
    missing_dbs = [db for db in cfg.db_names if db not in collections_by_db]
    if missing_dbs:
        print(f"[warn] DB(s) not found in collections config: {', '.join(missing_dbs)}", file=sys.stderr)
    if not requested_dbs:
        print("[error] No valid DB names to export.", file=sys.stderr)
        return 2

    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    exported: Dict[str, Dict[str, Any]] = {}

    try:
        client = MongoClient(cfg.mongo_uri, serverSelectionTimeoutMS=7000)
        client.admin.command("ping")
    except PyMongoError as exc:
        print(f"[error] Mongo connection failed: {exc}", file=sys.stderr)
        return 3

    for db_name in requested_dbs:
        db = client[db_name]
        exported[db_name] = {}
        collections = collections_by_db[db_name]
        sample_collection = pick_sample_collection(collections)
        selected_samples: List[Dict[str, Any]] = []
        sample_id_values: List[Any] = []
        sample_id_count = 0

        if sample_collection:
            sc = db[sample_collection]
            selected_samples, sample_id_count = select_latest_samples_per_assay(sc, cfg.sample_limit)
            for sample_doc in selected_samples:
                sample_oid = sample_doc.get("_id")
                if sample_oid is None:
                    continue
                sample_id_values.append(sample_oid)
                sample_id_values.append(str(sample_oid))
            print(
                f"[ok] {db_name}.{sample_collection}: selected {len(selected_samples)} samples "
                f"({cfg.sample_limit} per assay)"
            )
        else:
            print(f"[warn] {db_name}: no sample collection detected, SAMPLE_ID filtering disabled", file=sys.stderr)
        for coll in collections:
            c = db[coll]
            is_full = coll in cfg.full_collections
            try:
                if coll == sample_collection:
                    docs = selected_samples
                    export_mode = f"samples_latest_per_assay:{cfg.sample_limit}"
                elif is_full:
                    docs = list(c.find({}, sort=[("_id", 1)]))
                    export_mode = "full:forced"
                elif has_sample_id_field(c):
                    docs = list(c.find({"SAMPLE_ID": {"$in": sample_id_values}}, sort=[("_id", 1)]))
                    export_mode = f"by_sample_ids:{sample_id_count}"
                else:
                    docs = list(c.find({}, sort=[("_id", 1)]))
                    export_mode = "full:no_sample_id"
            except Exception:
                if coll == sample_collection:
                    docs = selected_samples
                    export_mode = f"samples_latest_per_assay:{cfg.sample_limit}"
                elif is_full:
                    docs = list(c.find({}))
                    export_mode = "full:forced"
                elif has_sample_id_field(c):
                    docs = list(c.find({"SAMPLE_ID": {"$in": sample_id_values}}))
                    export_mode = f"by_sample_ids:{sample_id_count}"
                else:
                    docs = list(c.find({}))
                    export_mode = "full:no_sample_id"
            try:
                indexes = list(c.list_indexes())
            except Exception:
                indexes = []

            coll_dir = cfg.out_dir / db_name
            docs_file = coll_dir / f"{coll}.ndjson"
            idx_file = coll_dir / f"{coll}.indexes.ndjson"
            write_ndjson(docs_file, docs)
            write_ndjson(idx_file, indexes)

            exported[db_name][coll] = {
                "docs_file": str(docs_file.relative_to(cfg.out_dir)),
                "indexes_file": str(idx_file.relative_to(cfg.out_dir)),
                "docs_count": len(docs),
                "indexes_count": len(indexes),
                "export_mode": export_mode,
            }
            print(f"[ok] {db_name}.{coll}: {len(docs)} docs, {len(indexes)} indexes")

    manifest = {
        "kind": "coyote3-mongo-micro-snapshot",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "mongo_uri": sanitize_uri(cfg.mongo_uri),
        "sample_limit": cfg.sample_limit,
        "sample_limit_semantics": "per_assay",
        "full_collections": sorted(cfg.full_collections),
        "dbs": exported,
    }
    (cfg.out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[done] Snapshot written to: {cfg.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
