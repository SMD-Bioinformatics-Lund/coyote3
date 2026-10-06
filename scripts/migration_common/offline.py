"""Index immutable legacy BSON exports and write validated, private migration bundles.

This module has no MongoDB connection. SQLite indexes bound memory use to the selected
sample rather than loading the source database into memory.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from bson import BSON, decode_file_iter, json_util
from pydantic import ValidationError

SOURCE_COLLECTIONS = {
    2: (
        "samples",
        "variants_idref",
        "cnvs_wgs",
        "fusions",
        "transloc",
        "biomarkers",
        "annotation",
        "blacklist",
    ),
    3: (
        "samples",
        "variants",
        "cnvs",
        "transloc",
        "biomarkers",
        "panel_cov",
        "group_coverage",
        "annotation",
        "blacklist",
        "reported_variants",
    ),
}
SAMPLE_COLLECTIONS = {
    2: {
        "variants_idref": "variants",
        "cnvs_wgs": "cnvs",
        "fusions": "fusions",
        "transloc": "translocations",
        "biomarkers": "biomarkers",
    },
    3: {
        "variants": "variants",
        "cnvs": "cnvs",
        "transloc": "translocations",
        "biomarkers": "biomarkers",
        "reported_variants": "reported_variants",
    },
}


class RecordConversionError(ValueError):
    """Carry private record coordinates without exposing clinical values in stderr."""

    def __init__(self, collection: str, original: dict, cause: Exception):
        """Record original identity and digest for an operator-owned issue file."""
        super().__init__(
            "A source record requires reconciliation; use --issues for private details"
        )
        self.issue = {
            "collection": collection,
            "source_id": original.get("_id"),
            "source_sha256": digest(original),
            "error": type(cause).__name__,
        }
        if isinstance(cause, ValidationError):
            self.issue["fields"] = [
                {"field": item["loc"], "error": item["type"]} for item in cause.errors()
            ]
        elif isinstance(cause, ValueError):
            self.issue["reason"] = str(cause)


def digest(value: Any) -> str:
    """Return a stable SHA-256 digest of BSON-aware values for reconciliation."""
    data = json_util.dumps(value, sort_keys=True, json_options=json_util.CANONICAL_JSON_OPTIONS)
    return hashlib.sha256(data.encode()).hexdigest()


def read_json(path: Path) -> Any:
    """Read an operator-owned Extended JSON file, preserving ObjectIds and dates."""
    return json_util.loads(path.read_text())


def private_json(path: Path, value: Any) -> None:
    """Create a private, exclusive Extended JSON artifact; never overwrite a prior run."""
    with path.open("x") as stream:
        os.chmod(path, 0o600)
        stream.write(json_util.dumps(value, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def prepare_source(export_dir: Path, index_path: Path, version: int) -> dict[str, int]:
    """Stream allowlisted BSON files into a local, indexed source snapshot.

    Args:
        export_dir: A single database directory from an operator-provided BSON dump.
            Every collection in the version's inventory must have a file, even if empty.
        index_path: New SQLite file outside the repository; existing files are refused.
        version: Source major version, 2 or 3. V2 excludes variants and cnvs.

    Returns:
        Source counts by physical collection name.

    Raises:
        ValueError: A source identity, sample relationship, or required file is missing.
        FileExistsError: The index already exists.
    """
    collections = SOURCE_COLLECTIONS[version]
    if any(not (export_dir / f"{name}.bson").is_file() for name in collections):
        raise ValueError("Source export is incomplete; all documented BSON files are required")
    descriptor = os.open(index_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    counts = {}
    with sqlite3.connect(index_path) as connection:
        connection.executescript(
            "CREATE TABLE metadata (version INTEGER, complete INTEGER);"
            "CREATE TABLE documents (collection TEXT, identity TEXT, sample_ref TEXT, "
            "sample_name TEXT, payload BLOB, PRIMARY KEY(collection, identity));"
            "CREATE INDEX sample_lookup ON documents(collection, sample_ref);"
            "CREATE TABLE samples (identity TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL);"
            "CREATE TABLE inventory (collection TEXT PRIMARY KEY, count INTEGER, sha256 TEXT);"
        )
        connection.execute("INSERT INTO metadata VALUES (?, 0)", (version,))
        for name in collections:
            count = 0
            checksum = hashlib.sha256()
            with (export_dir / f"{name}.bson").open("rb") as stream:
                for document in decode_file_iter(stream):
                    if document.get("_id") is None:
                        raise ValueError("Source record has no original identity")
                    identity = str(document["_id"])
                    payload = BSON.encode(document)
                    checksum.update(payload)
                    sample_ref = document.get("SAMPLE_ID", document.get("sample_oid"))
                    connection.execute(
                        "INSERT INTO documents VALUES (?, ?, ?, ?, ?)",
                        (
                            name,
                            identity,
                            str(sample_ref) if sample_ref is not None else None,
                            document.get("sample"),
                            payload,
                        ),
                    )
                    if name == "samples":
                        connection.execute(
                            "INSERT INTO samples VALUES (?, ?)", (identity, document["name"])
                        )
                    count += 1
                    if count % 10000 == 0:
                        connection.commit()
            connection.execute(
                "INSERT INTO inventory VALUES (?, ?, ?)", (name, count, checksum.hexdigest())
            )
            counts[name] = count
        related = list(SAMPLE_COLLECTIONS[version])
        if version == 3:
            related.append("panel_cov")
            # group_coverage can contain both sample measurements and group exclusions.
            for row in connection.execute(
                "SELECT payload FROM documents WHERE collection='group_coverage'"
            ):
                document = BSON(row[0]).decode()
                if "genes" in document:
                    reference = str(document.get("SAMPLE_ID", ""))
                    match = connection.execute(
                        "SELECT name FROM samples WHERE identity=?", (reference,)
                    ).fetchone()
                    if match is None or document.get("sample") != match[0]:
                        raise ValueError("Group coverage has an orphan or conflicting sample")
        for name in related:
            orphan = connection.execute(
                "SELECT 1 FROM documents d LEFT JOIN samples s ON d.sample_ref=s.identity "
                "WHERE d.collection=? AND (s.identity IS NULL OR "
                "(d.sample_name IS NOT NULL AND d.sample_name<>s.name)) LIMIT 1",
                (name,),
            ).fetchone()
            if orphan:
                raise ValueError("Source contains orphan or conflicting sample references")
        connection.execute("UPDATE metadata SET complete=1")
    return counts


class SourceIndex:
    """Expose only read queries against a completed local source snapshot."""

    def __init__(self, path: Path, version: int):
        """Open a completed index read-only and reject the wrong source version."""
        self.connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        if self.connection.execute("SELECT version, complete FROM metadata").fetchall() != [
            (version, 1)
        ]:
            self.connection.close()
            raise ValueError("Source index is incomplete or belongs to another version")
        self.version = version

    def close(self) -> None:
        """Release the read-only SQLite connection."""
        self.connection.close()

    def rows(self, collection: str, sample_id: str | None = None) -> Iterator[dict]:
        """Yield original BSON records, optionally restricted to one source sample ID."""
        query = "SELECT payload FROM documents WHERE collection=?"
        params = [collection]
        if sample_id is not None:
            query += " AND sample_ref=?"
            params.append(sample_id)
        for (payload,) in self.connection.execute(query + " ORDER BY identity", params):
            yield BSON(payload).decode()

    def get(self, collection: str, identity: str) -> dict:
        """Read one original record by identity; fail when the reference is absent."""
        row = self.connection.execute(
            "SELECT payload FROM documents WHERE collection=? AND identity=?",
            (collection, identity),
        ).fetchone()
        if row is None:
            raise ValueError("Referenced source record is missing")
        return BSON(row[0]).decode()

    def fingerprint(self) -> str:
        """Return the versioned source inventory digest recorded during preparation."""
        return digest(
            [
                self.version,
                self.connection.execute(
                    "SELECT collection, count, sha256 FROM inventory ORDER BY collection"
                ).fetchall(),
            ]
        )


def write_bundle(
    output: Path, documents: dict[str, list[dict]], *, provenance: dict[str, Any]
) -> dict[str, int]:
    """Write an exclusive BSON bundle and manifest after conversion has succeeded.

    Args:
        output: New private directory, never a source export directory.
        documents: Validated destination documents grouped by collection.
        provenance: Source inventory hash and reviewed mapping evidence.

    Returns:
        Destination counts. A manifest is written last; its absence means incomplete output.
    """
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    inventory = {}
    for name, rows in sorted(documents.items()):
        if not name.replace("_", "").isalnum():
            raise ValueError("Invalid destination collection")
        checksum = hashlib.sha256()
        with (output / f"{name}.bson").open("xb") as stream:
            os.chmod(stream.name, 0o600)
            for row in rows:
                encoded = BSON.encode(row)
                checksum.update(encoded)
                stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        inventory[name] = {"count": len(rows), "sha256": checksum.hexdigest()}
    private_json(
        output / "manifest.json", {"format": 1, "collections": inventory, "provenance": provenance}
    )
    return {name: entry["count"] for name, entry in inventory.items()}
