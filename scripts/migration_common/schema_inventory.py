"""Inventory every nested BSON field in an offline legacy export without sampling."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from bson import BSON, decode_file_iter

from scripts.migration_common.offline import (
    SOURCE_COLLECTIONS,
    SourceIndex,
    digest,
    private_json,
    read_json,
)


def observe(document: dict) -> tuple[set[str], Counter, Counter]:
    """Count paths, BSON types, and exact object-key shapes throughout one document.

    Args:
        document: One decoded source record. Values and identifiers are not returned.

    Returns:
        Paths present in this record, occurrence counts by path/type, and object-shape
        counts. Paths are JSON arrays of tagged field/array components, avoiding
        collisions with literal dots, brackets, or wildcard characters in field names.
        Array members are all visited; empty arrays still have an array occurrence.
    """
    present, types, shapes = set(), Counter(), Counter()
    pending = [((), document)]
    while pending:
        components, value = pending.pop()
        path = json.dumps(components, separators=(",", ":"))
        present.add(path)
        # BSON's own encoder distinguishes null, bool, int32/int64, dates, ObjectId,
        # binary subtypes, decimal, regex, arrays, documents, and other BSON values.
        kind = "0x03" if isinstance(value, dict) else "0x04" if isinstance(value, list) else None
        if kind is None:
            kind = f"0x{BSON.encode({'v': value})[4]:02x}"
        if kind == "0x05":
            kind += f":subtype={getattr(value, 'subtype', 0)}"
        types[(path, kind)] += 1
        if isinstance(value, dict):
            shape = json.dumps(sorted(value), separators=(",", ":"))
            shapes[(path, shape)] += 1
            pending.extend((components + (("field", key),), item) for key, item in value.items())
        elif isinstance(value, list):
            pending.extend((components + (("array",),), item) for item in value)
    return present, types, shapes


def flush_statistics(
    connection: sqlite3.Connection, name: str, presence: Counter, types: Counter, shapes: Counter
) -> None:
    """Merge bounded batches into disk-backed counters without losing rare paths."""
    connection.executemany(
        "INSERT INTO paths VALUES (?,?,?) ON CONFLICT(collection,path) "
        "DO UPDATE SET documents_present=documents_present+excluded.documents_present",
        ((name, path, number) for path, number in presence.items()),
    )
    for table, records, column in (("types", types, "bson_type"), ("shapes", shapes, "fields")):
        connection.executemany(
            f"INSERT INTO {table} VALUES (?,?,?,?) ON CONFLICT(collection,path,{column}) "
            "DO UPDATE SET occurrences=occurrences+excluded.occurrences",
            ((name, path, detail, number) for (path, detail), number in records.items()),
        )
    connection.commit()
    presence.clear()
    types.clear()
    shapes.clear()


def inventory_export(export_dir: Path, output: Path, version: int) -> dict:
    """Stream every record in every migrated collection into a disk-backed schema inventory.

    Args:
        export_dir: Local directory of uncompressed source BSON files.
        output: New private directory for schema.sqlite and a completion manifest.
        version: Source major version, determining the explicit clinical collection scope.

    Returns:
        Completion manifest binding the audit to exact source collection counts and hashes.

    Raises:
        ValueError: A required export is missing. Invalid BSON stops the scan.
        FileExistsError: The output directory already exists.

    Notes:
        No MongoDB connection is made. A manifest is written only after every record
        has been visited. Field names themselves may contain sensitive information.
    """
    names = SOURCE_COLLECTIONS[version]
    if any(not (export_dir / f"{name}.bson").is_file() for name in names):
        raise ValueError("Full schema inventory requires every version-specific BSON export")
    output.mkdir(mode=0o700, exist_ok=False)
    database = output / "schema.sqlite"
    descriptor = os.open(database, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    inventory = []
    with sqlite3.connect(database) as connection:
        connection.executescript(
            "CREATE TABLE collections (name TEXT PRIMARY KEY, documents INTEGER);"
            "CREATE TABLE paths (collection TEXT, path TEXT, documents_present INTEGER, "
            "PRIMARY KEY(collection,path));"
            "CREATE TABLE types (collection TEXT, path TEXT, bson_type TEXT, occurrences INTEGER, "
            "PRIMARY KEY(collection,path,bson_type));"
            "CREATE TABLE shapes (collection TEXT, path TEXT, fields TEXT, occurrences INTEGER, "
            "PRIMARY KEY(collection,path,fields));"
            "CREATE VIEW field_presence AS SELECT p.*, c.documents-p.documents_present "
            "AS documents_missing FROM paths p JOIN collections c ON p.collection=c.name;"
        )
        for name in names:
            count, checksum = 0, hashlib.sha256()
            presence_batch, type_batch, shape_batch = Counter(), Counter(), Counter()
            with (export_dir / f"{name}.bson").open("rb") as stream:
                for document in decode_file_iter(stream):
                    checksum.update(BSON.encode(document))
                    present, types, shapes = observe(document)
                    presence_batch.update(present)
                    type_batch.update(types)
                    shape_batch.update(shapes)
                    count += 1
                    if (
                        count % 1000 == 0
                        or len(presence_batch) + len(type_batch) + len(shape_batch) >= 10000
                    ):
                        flush_statistics(connection, name, presence_batch, type_batch, shape_batch)
            flush_statistics(connection, name, presence_batch, type_batch, shape_batch)
            connection.execute("INSERT INTO collections VALUES (?,?)", (name, count))
            inventory.append((name, count, checksum.hexdigest()))
    with database.open("rb") as stream:
        report_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    manifest = {
        "format": 1,
        "source_version": version,
        "complete": True,
        "source_sha256": digest([version, sorted(inventory)]),
        "schema_sha256": report_hash,
        "collections": {
            name: {"count": count, "sha256": checksum} for name, count, checksum in inventory
        },
        "unprofiled_files": sorted(
            path.name for path in export_dir.glob("*.bson") if path.stem not in names
        ),
    }
    private_json(output / "manifest.json", manifest)
    return manifest


def verify_review(source: SourceIndex, audit: Path, review: dict[str, Any]) -> str:
    """Require a complete matching inventory and an explicit operator schema review.

    Args:
        source: Prepared source index used for conversion.
        audit: Completed full inventory directory for the same source snapshot.
        review: Operator review containing schema_audit with manifest_sha256,
            reviewed_by, reviewed_on, and dispositions for every unprofiled file.

    Returns:
        Manifest digest included in the destination bundle's provenance.

    Raises:
        ValueError: Inventory is incomplete, stale, altered, or lacks review evidence.
    """
    manifest = read_json(audit / "manifest.json")
    if (
        manifest.get("format") != 1
        or manifest.get("complete") is not True
        or manifest.get("source_sha256") != source.fingerprint()
        or manifest.get("source_version") != source.version
    ):
        raise ValueError("Full schema inventory does not match this source snapshot")
    with (audit / "schema.sqlite").open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != manifest.get("schema_sha256"):
            raise ValueError("Schema inventory was altered after completion")
    identity = digest(manifest)
    evidence = review.get("schema_audit", {})
    if (
        evidence.get("manifest_sha256") != identity
        or not evidence.get("reviewed_by")
        or not evidence.get("reviewed_on")
    ):
        raise ValueError("Full schema inventory requires recorded operator review")
    exclusions = evidence.get("unprofiled_files", {})
    if any(not exclusions.get(name) for name in manifest.get("unprofiled_files", [])):
        raise ValueError("Every unprofiled export requires an explicit scope disposition")
    return identity


def main(version: int) -> int:
    """Run the complete offline inventory and print only counts and the review digest."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = inventory_export(args.export_dir, args.output, version)
        print(
            json.dumps(
                {
                    "manifest_sha256": digest(manifest),
                    "documents": {
                        name: row["count"] for name, row in manifest["collections"].items()
                    },
                }
            )
        )
        return 0
    except Exception as error:
        print(f"Full inventory incomplete: {type(error).__name__}", file=sys.stderr)
        return 1
