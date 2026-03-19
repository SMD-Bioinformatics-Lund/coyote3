#!/usr/bin/env python3
"""Create a focused MongoDB snapshot for mixed-assay sample validation.

Rules:
1) Select a mixed-assay cohort of samples (default: 60).
2) For collections that contain `SAMPLE_ID`, export only rows for selected samples.
3) For collections without `SAMPLE_ID`, export full collection content.
"""

from __future__ import annotations

import argparse
import json
import random
import tomllib
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bson import ObjectId, json_util
from pymongo import MongoClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create mixed-assay MongoDB snapshot.")
    parser.add_argument("--mongo-uri", default="mongodb://localhost:27017")
    parser.add_argument("--db", required=True, help="Database name (e.g., coyote3_dev)")
    parser.add_argument(
        "--collections-config",
        default="config/coyote3_collections.toml",
        help="Path to collections TOML mapping",
    )
    parser.add_argument(
        "--config-section",
        default="",
        help="TOML section override. Defaults to --db value.",
    )
    parser.add_argument(
        "--sample-count",
        type=int,
        default=60,
        help="Target number of mixed-assay samples (recommended 50-60).",
    )
    parser.add_argument(
        "--sample-name",
        action="append",
        default=[],
        help="Explicit sample name to include. Repeatable.",
    )
    parser.add_argument(
        "--sample-id",
        action="append",
        default=[],
        help="Explicit sample _id to include (ObjectId hex or literal string). Repeatable.",
    )
    parser.add_argument(
        "--sample-list-file",
        default="",
        help="Path to newline-delimited explicit sample selectors (name or _id).",
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed for deterministic selection"
    )
    parser.add_argument(
        "--output-dir",
        default="snapshots",
        help="Base output directory. A timestamped child directory is created.",
    )
    return parser.parse_args()


def load_collection_names(config_path: Path, section: str) -> list[str]:
    with config_path.open("rb") as fh:
        payload = tomllib.load(fh)
    if section not in payload:
        raise KeyError(f"Section '{section}' not found in {config_path}")

    names: list[str] = []
    seen: set[str] = set()
    for key, value in payload[section].items():
        if not key.endswith("_collection"):
            continue
        if not isinstance(value, str):
            continue
        col_name = value.strip()
        if not col_name or col_name in seen:
            continue
        seen.add(col_name)
        names.append(col_name)
    return names


def select_mixed_samples(
    samples: list[dict[str, Any]], target_count: int, seed: int
) -> list[dict[str, Any]]:
    if target_count <= 0 or not samples:
        return []

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for doc in samples:
        assay = str(doc.get("assay") or "unknown").strip() or "unknown"
        grouped[assay].append(doc)

    rng = random.Random(seed)
    for rows in grouped.values():
        rng.shuffle(rows)

    assay_order = sorted(grouped.keys(), key=lambda key: (-len(grouped[key]), key))
    selected: list[dict[str, Any]] = []
    while len(selected) < min(target_count, len(samples)):
        progressed = False
        for assay in assay_order:
            rows = grouped[assay]
            if not rows:
                continue
            selected.append(rows.pop())
            progressed = True
            if len(selected) >= min(target_count, len(samples)):
                break
        if not progressed:
            break
    return selected


def _normalize_selector_values(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text or text.startswith("#") or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _load_selector_file(path: str) -> list[str]:
    if not path:
        return []
    out: list[str] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        out.append(line.strip())
    return _normalize_selector_values(out)


def resolve_explicit_samples(
    db,
    sample_names: list[str],
    sample_ids: list[str],
    sample_list_file: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    file_values = _load_selector_file(sample_list_file)
    merged_names = _normalize_selector_values(sample_names)
    merged_ids = _normalize_selector_values(sample_ids)
    # For file selectors, try matching by both name and _id string.
    for item in file_values:
        merged_names.append(item)
        merged_ids.append(item)
    merged_names = _normalize_selector_values(merged_names)
    merged_ids = _normalize_selector_values(merged_ids)

    if not merged_names and not merged_ids:
        return [], []

    id_literals: list[str] = []
    id_oids: list[ObjectId] = []
    for value in merged_ids:
        id_literals.append(value)
        if ObjectId.is_valid(value):
            id_oids.append(ObjectId(value))

    query_or: list[dict[str, Any]] = []
    if merged_names:
        query_or.append({"name": {"$in": merged_names}})
    if id_literals:
        query_or.append({"_id": {"$in": id_literals}})
    if id_oids:
        query_or.append({"_id": {"$in": id_oids}})

    sample_projection = {"_id": 1, "name": 1, "assay": 1, "profile": 1}
    docs = list(db["samples"].find({"$or": query_or}, sample_projection)) if query_or else []

    found_tokens: set[str] = set()
    for doc in docs:
        found_tokens.add(str(doc.get("_id")))
        found_tokens.add(str(doc.get("name") or ""))

    requested_tokens = _normalize_selector_values(merged_names + merged_ids)
    missing = [token for token in requested_tokens if token not in found_tokens]
    return docs, missing


def sample_scope_values(selected_samples: list[dict[str, Any]]) -> list[Any]:
    values: list[Any] = []
    seen: set[str] = set()
    for sample in selected_samples:
        oid = sample.get("_id")
        if oid is None:
            continue
        as_str = str(oid)
        if as_str not in seen:
            values.append(as_str)
            seen.add(as_str)
        # Include raw _id too in case SAMPLE_ID is stored as ObjectId in some collections.
        raw_marker = f"raw::{repr(oid)}"
        if raw_marker not in seen:
            values.append(oid)
            seen.add(raw_marker)
    return values


def collection_has_sample_id(db, collection_name: str) -> bool:
    return db[collection_name].find_one({"SAMPLE_ID": {"$exists": True}}, {"_id": 1}) is not None


def export_collection(db, collection_name: str, out_file: Path, query: dict[str, Any]) -> int:
    count = 0
    with out_file.open("w", encoding="utf-8") as fh:
        for doc in db[collection_name].find(query):
            fh.write(json_util.dumps(doc))
            fh.write("\n")
            count += 1
    return count


def main() -> int:
    args = parse_args()
    config_path = Path(args.collections_config)
    config_section = args.config_section.strip() or args.db

    collection_names = load_collection_names(config_path, config_section)
    if not collection_names:
        raise SystemExit(f"No collections found in section '{config_section}'")

    sample_collection = "samples"
    if sample_collection not in collection_names:
        collection_names.append(sample_collection)

    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=7000)
    client.admin.command("ping")
    db = client[args.db]

    explicit_samples, missing_selectors = resolve_explicit_samples(
        db,
        sample_names=args.sample_name,
        sample_ids=args.sample_id,
        sample_list_file=args.sample_list_file,
    )
    if explicit_samples:
        selected_samples = explicit_samples
        selection_mode = "explicit"
    else:
        sample_projection = {"_id": 1, "name": 1, "assay": 1, "profile": 1}
        all_samples = list(db[sample_collection].find({}, sample_projection))
        selected_samples = select_mixed_samples(all_samples, args.sample_count, args.seed)
        selection_mode = "mixed_assay_random"
    sample_ids = sample_scope_values(selected_samples)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_root = Path(args.output_dir) / f"{args.db}_snapshot_{timestamp}"
    out_root.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "mongo_uri": args.mongo_uri,
        "db": args.db,
        "config_section": config_section,
        "created_at_utc": timestamp,
        "sample_count_requested": args.sample_count,
        "sample_count_selected": len(selected_samples),
        "selection_mode": selection_mode,
        "missing_sample_selectors": missing_selectors,
        "collections": [],
        "selected_samples": [
            {
                "_id": str(sample.get("_id")),
                "name": sample.get("name"),
                "assay": sample.get("assay"),
                "profile": sample.get("profile"),
            }
            for sample in selected_samples
        ],
    }

    for collection_name in collection_names:
        if collection_name not in db.list_collection_names():
            manifest["collections"].append(
                {
                    "collection": collection_name,
                    "exists": False,
                    "mode": "missing",
                    "query": {},
                    "exported_docs": 0,
                    "file": None,
                }
            )
            continue

        has_sample_id = collection_has_sample_id(db, collection_name)
        query: dict[str, Any]
        mode: str
        if has_sample_id:
            query = {"SAMPLE_ID": {"$in": sample_ids}}
            mode = "sample_scoped"
        else:
            query = {}
            mode = "full_collection"

        out_file = out_root / f"{collection_name}.jsonl"
        exported = export_collection(db, collection_name, out_file, query)
        manifest["collections"].append(
            {
                "collection": collection_name,
                "exists": True,
                "has_sample_id": has_sample_id,
                "mode": mode,
                "query": query,
                "exported_docs": exported,
                "file": out_file.name,
            }
        )

    with (out_root / "manifest.json").open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, default=str)

    print(f"[ok] snapshot written: {out_root}")
    print(
        f"[ok] selected_samples={len(selected_samples)} "
        f"collections_exported={sum(1 for c in manifest['collections'] if c['exists'])}"
    )
    if missing_selectors:
        print(f"[warn] missing_sample_selectors={len(missing_selectors)} -> {missing_selectors}")
    print(f"SNAPSHOT_DIR={out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
