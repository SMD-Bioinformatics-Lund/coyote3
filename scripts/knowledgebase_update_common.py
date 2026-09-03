#!/usr/bin/env python3
"""Shared primitives for manual knowledgebase snapshot updates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import tomllib
from collections.abc import Callable, Iterable, Iterator, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pymongo import IndexModel, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError

from api.config.paths import COLLECTIONS_CONFIG_PATH

BATCH_SIZE = 5_000
MAX_SOURCE_FIELD_BYTES = 16 * 1024 * 1024
VERSIONS_COLLECTION = "versions"
STAGE_PREFIX = "__kb_stage__"
BACKUP_PREFIX = "__kb_previous__"
EMPTY_VALUES = {"", "-", "NA", "N/A", "NR", "NS", "null", "None"}

csv.field_size_limit(MAX_SOURCE_FIELD_BYTES)


@dataclass(frozen=True)
class CollectionSpec:
    """One stable collection produced by a knowledgebase release."""

    name: str
    documents: Callable[[], Iterator[dict[str, Any]]]
    indexes: tuple[tuple[tuple[tuple[str, int], ...], dict[str, Any]], ...]


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """Add consistent connection and publication arguments to an updater."""
    parser.add_argument("--mongo-uri", default=os.getenv("MONGO_URI", ""))
    parser.add_argument("--database", default=os.getenv("KNOWLEDGEBASE_DB", ""))
    parser.add_argument("--release", required=True, help="Upstream release identifier.")
    parser.add_argument(
        "--cpus",
        type=int,
        default=1,
        help="Concurrent validation and MongoDB batch workers (default: 1).",
    )
    parser.add_argument(
        "--collections-config",
        type=Path,
        default=COLLECTIONS_CONFIG_PATH,
        help="Collection mapping TOML.",
    )
    parser.add_argument("--apply", action="store_true", help="Import and publish the release.")
    parser.add_argument(
        "--drop-previous",
        action="store_true",
        help="Drop replaced collections after every new collection has published successfully.",
    )
    parser.add_argument(
        "--report", type=Path, help="Write the non-sensitive update report as JSON."
    )


def require_apply_settings(args: argparse.Namespace) -> None:
    """Validate settings needed only when MongoDB will be modified."""
    if args.cpus < 1:
        raise ValueError("--cpus must be at least 1")
    if args.drop_previous and not args.apply:
        raise ValueError("--drop-previous requires --apply")
    if args.apply and (not args.mongo_uri or not args.database):
        raise ValueError("--mongo-uri/MONGO_URI and --database/KNOWLEDGEBASE_DB are required")


def knowledgebase_mapping(path: Path) -> dict[str, str]:
    """Load the authoritative logical-to-physical knowledgebase mapping."""
    with path.open("rb") as handle:
        payload = tomllib.load(handle)
    mapping = payload.get("knowledgebase")
    if not isinstance(mapping, dict):
        raise ValueError(f"[knowledgebase] is missing from {path}")
    return {str(key): str(value) for key, value in mapping.items()}


def mapped_collection(args: argparse.Namespace, logical_key: str) -> str:
    """Resolve a required physical collection from the configured mapping."""
    value = knowledgebase_mapping(args.collections_config).get(logical_key, "").strip()
    if not value:
        raise ValueError(f"Knowledgebase collection mapping is missing: {logical_key}")
    return value


def clean_text(value: Any) -> str | None:
    """Return meaningful source text without manufacturing a replacement value."""
    if value is None:
        return None
    result = str(value).strip()
    return None if result in EMPTY_VALUES else result


def parse_int(value: Any) -> int | None:
    """Parse a source integer while preserving missing values as missing."""
    text = clean_text(value)
    if text is None:
        return None
    return int(float(text))


def parse_float(value: Any) -> float | None:
    """Parse a source number while preserving missing values as missing."""
    text = clean_text(value)
    if text is None:
        return None
    return float(text)


def split_values(value: Any, separator: str = ",") -> list[str]:
    """Split a source list and discard only empty markers."""
    text = clean_text(value)
    if text is None:
        return []
    return [part.strip() for part in text.split(separator) if clean_text(part) is not None]


def snake_case(value: str) -> str:
    """Convert an upstream heading to a stable lowercase field name."""
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", value.strip()).strip("_")
    normalized = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", normalized)
    return normalized.lower()


def without_missing(values: dict[str, Any]) -> dict[str, Any]:
    """Remove missing values without treating zero or false as missing."""
    return {key: value for key, value in values.items() if value is not None}


def source_fields(row: dict[str, Any], *, exclude: set[str] | None = None) -> dict[str, str]:
    """Preserve non-empty upstream fields under their original headings."""
    excluded = exclude or set()
    return {
        key: text
        for key, value in row.items()
        if key not in excluded and (text := clean_text(value)) is not None
    }


def delimited_rows(path: Path) -> Iterator[tuple[int, dict[str, str]]]:
    """Read a CSV or TSV snapshot with delimiter detection and line numbers."""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(64 * 1024)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters="\t,")
        except csv.Error:
            dialect = csv.excel_tab
        reader = csv.DictReader(handle, dialect=dialect)
        if not reader.fieldnames:
            raise ValueError(f"Source file has no header: {path}")
        for line_number, row in enumerate(reader, start=2):
            yield line_number, {str(key): value for key, value in row.items() if key is not None}


def file_manifest(path: Path) -> dict[str, Any]:
    """Calculate immutable provenance for one operator-supplied source file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    stat = path.stat()
    return {
        "name": path.name,
        "size_bytes": stat.st_size,
        "sha256": digest.hexdigest(),
    }


def record_key(*parts: Any) -> str:
    """Build a deterministic key for source records without a stable identifier."""
    canonical = json.dumps(parts, ensure_ascii=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _stage_name(collection: str, run_id: str) -> str:
    return f"{STAGE_PREFIX}{collection}__{run_id}"


def _backup_name(collection: str, run_id: str) -> str:
    return f"{BACKUP_PREFIX}{collection}__{run_id}"


def _insert_batch(collection: Collection, batch: list[dict[str, Any]]) -> int:
    collection.insert_many(batch, ordered=False)
    return len(batch)


def _insert_documents(
    collection: Collection,
    documents: Iterable[dict[str, Any]],
    *,
    cpus: int,
) -> int:
    """Insert bounded batches with concurrent MongoDB writers."""
    count = 0
    batch: list[dict[str, Any]] = []
    pending: list[Future[int]] = []
    max_pending = cpus * 2
    with ThreadPoolExecutor(max_workers=cpus, thread_name_prefix="kb-insert") as executor:
        for document in documents:
            batch.append(document)
            if len(batch) < BATCH_SIZE:
                continue
            pending.append(executor.submit(_insert_batch, collection, batch))
            batch = []
            if len(pending) >= max_pending:
                count += pending.pop(0).result()
        if batch:
            pending.append(executor.submit(_insert_batch, collection, batch))
        for future in pending:
            count += future.result()
    return count


def _create_indexes(collection: Collection, spec: CollectionSpec) -> list[str]:
    if not spec.indexes:
        return []
    return collection.create_indexes(
        [IndexModel(list(keys), **options) for keys, options in spec.indexes]
    )


def _inspect_spec(spec: CollectionSpec) -> dict[str, Any]:
    count = sum(1 for _ in spec.documents())
    if count == 0:
        raise ValueError(f"Parsed collection would be empty: {spec.name}")
    return {"collection": spec.name, "documents": count, "status": "validated"}


def inspect_specs(specs: Sequence[CollectionSpec], *, cpus: int) -> list[dict[str, Any]]:
    """Parse every selected source completely without writing to MongoDB."""
    with ThreadPoolExecutor(
        max_workers=min(cpus, len(specs)),
        thread_name_prefix="kb-validate",
    ) as executor:
        return list(executor.map(_inspect_spec, specs))


def publish_release(
    database: Database,
    *,
    source: str,
    release: str,
    files: Sequence[dict[str, Any]],
    specs: Sequence[CollectionSpec],
    drop_previous: bool,
    cpus: int = 1,
    extra_metadata: dict[str, Any] | None = None,
    versions_collection: str = VERSIONS_COLLECTION,
) -> dict[str, Any]:
    """Stage, validate, and publish a complete upstream snapshot."""
    now = datetime.now(UTC)
    run_id = now.strftime("%Y%m%dT%H%M%S%fZ")
    release_id = f"{source}:{release}"
    releases = database[versions_collection]
    releases.create_index([("source", 1), ("release", 1)], unique=True, name="source_release")
    releases.create_index([("source", 1), ("status", 1)], name="source_status")
    if releases.find_one({"source": source, "release": release, "status": "active"}):
        raise ValueError(f"Release is already active: {release_id}")

    collection_names = set(database.list_collection_names())
    stage_names = {spec.name: _stage_name(spec.name, run_id) for spec in specs}
    backup_names = {spec.name: _backup_name(spec.name, run_id) for spec in specs}
    conflicts = sorted(
        name for name in (*stage_names.values(), *backup_names.values()) if name in collection_names
    )
    if conflicts:
        raise RuntimeError(f"Migration namespaces already exist: {', '.join(conflicts)}")

    manifest = {
        "_id": release_id,
        "source": source,
        "release": release,
        "status": "staging",
        "started_at": now,
        "files": list(files),
        "import_cpus": cpus,
        "collections": [],
        **(extra_metadata or {}),
    }
    releases.replace_one({"_id": release_id}, manifest, upsert=True)

    staged: list[str] = []
    published: list[str] = []
    replaced: list[str] = []
    try:
        for spec in specs:
            stage_name = stage_names[spec.name]
            stage = database[stage_name]
            count = _insert_documents(stage, spec.documents(), cpus=cpus)
            if count == 0:
                raise ValueError(f"Parsed collection would be empty: {spec.name}")
            index_names = _create_indexes(stage, spec)
            if stage.count_documents({}) != count:
                raise RuntimeError(f"Inserted count verification failed: {spec.name}")
            staged.append(spec.name)
            manifest["collections"].append(
                {"name": spec.name, "documents": count, "indexes": index_names}
            )
            releases.update_one(
                {"_id": release_id}, {"$set": {"collections": manifest["collections"]}}
            )

        for spec in specs:
            if spec.name in collection_names:
                database[spec.name].rename(backup_names[spec.name], dropTarget=False)
                replaced.append(spec.name)
            database[stage_names[spec.name]].rename(spec.name, dropTarget=False)
            published.append(spec.name)

        releases.update_many(
            {"source": source, "status": "active", "_id": {"$ne": release_id}},
            {"$set": {"status": "retired", "retired_at": datetime.now(UTC)}},
        )
        releases.update_one(
            {"_id": release_id},
            {
                "$set": {
                    "status": "active",
                    "published_at": datetime.now(UTC),
                    "collections": manifest["collections"],
                }
            },
        )
    except Exception:
        for spec in reversed(specs):
            name = spec.name
            existing = set(database.list_collection_names())
            if name in published and name in existing:
                database[name].rename(stage_names[name], dropTarget=True)
                existing = set(database.list_collection_names())
            if name in replaced and backup_names[name] in existing:
                database[backup_names[name]].rename(name, dropTarget=False)
            if stage_names[name] in database.list_collection_names():
                database.drop_collection(stage_names[name])
        releases.update_one(
            {"_id": release_id},
            {"$set": {"status": "failed", "failed_at": datetime.now(UTC)}},
        )
        raise

    dropped: list[str] = []
    if drop_previous:
        for name in replaced:
            database.drop_collection(backup_names[name])
            dropped.append(name)

    return {
        "source": source,
        "release": release,
        "status": "active",
        "collections": manifest["collections"],
        "previous_collections_retained": sorted(set(replaced) - set(dropped)),
        "previous_collections_dropped": dropped,
    }


def execute_update(
    args: argparse.Namespace,
    *,
    source: str,
    paths: Sequence[Path],
    specs: Sequence[CollectionSpec],
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a dry validation or publish a release and close MongoDB reliably."""
    require_apply_settings(args)
    for path in paths:
        if not path.is_file():
            raise ValueError(f"Source file does not exist: {path}")
    with ThreadPoolExecutor(
        max_workers=min(args.cpus, len(paths)),
        thread_name_prefix="kb-hash",
    ) as executor:
        files = list(executor.map(file_manifest, paths))
    if not args.apply:
        return {
            "source": source,
            "release": args.release,
            "status": "validated",
            "files": files,
            "collections": inspect_specs(specs, cpus=args.cpus),
            "cpus": args.cpus,
        }

    client = MongoClient(
        args.mongo_uri,
        serverSelectionTimeoutMS=10_000,
        maxPoolSize=max(10, args.cpus * 2),
    )
    try:
        client.admin.command("ping")
        return publish_release(
            client[args.database],
            source=source,
            release=args.release,
            files=files,
            specs=specs,
            drop_previous=args.drop_previous,
            cpus=args.cpus,
            extra_metadata=extra_metadata,
            versions_collection=mapped_collection(args, "knowledgebase_versions_collection"),
        )
    finally:
        client.close()


def finish_command(args: argparse.Namespace, runner: Callable[[], dict[str, Any]]) -> int:
    """Render a consistent command result and optional report."""
    try:
        report = runner()
    except (csv.Error, OSError, PyMongoError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 2
    rendered = json.dumps(report, indent=2, default=str)
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(f"{rendered}\n", encoding="utf-8")
    return 0
