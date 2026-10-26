#!/usr/bin/env python3
"""Export an assay's samples and sample-owned collections in resumable, read-only batches."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from bson import ObjectId, json_util

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from migrations_scripts.common import assay_query, fingerprint, matches_source  # noqa: E402
from migrations_scripts.related import file_hash, json_rows  # noqa: E402

Document = dict[str, Any]
OWNER_FIELDS = ("SAMPLE_ID", "sample_oid")


def mongo_query(value: Any) -> Any:
    """Encode shared assay regex predicates for the MongoDB 3.2 query parser.

    Args:
        value: Nested predicate containing Python case-insensitive regex objects.

    Returns:
        JSON-compatible query using $regex/$options rather than modern Extended JSON.
    """
    if isinstance(value, re.Pattern):
        return {"$regex": value.pattern, "$options": "i" if value.flags & re.IGNORECASE else ""}
    if isinstance(value, dict):
        return {key: mongo_query(item) for key, item in value.items()}
    if isinstance(value, list):
        return [mongo_query(item) for item in value]
    return value


def write_json(path: Path, document: Document) -> None:
    """Atomically replace a local checkpoint after its data files have been closed.

    Args:
        path: Checkpoint in the protected output directory.
        document: JSON-compatible progress or completion metadata.
    """
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(document, indent=2) + "\n")
    temporary.replace(path)


class Source:
    """Run only legacy MongoDB reads, locally or through an explicitly selected SSH host."""

    def __init__(self, args: argparse.Namespace) -> None:
        """Bind the source database and connection tools without opening a connection.

        Args:
            args: CLI configuration; no destination database or write operation exists.
        """
        self.args = args
        self.database = "coyote" if args.source_version == 2 else "coyote3"

    def execute(self, command: list[str], output: Path, script: str | None = None) -> None:
        """Stream a read command to a protected file without exposing source data in logs.

        Args:
            command: Argument vector for mongo or mongoexport, never a shell command string.
            output: Local data file; its sibling .stderr file captures private diagnostics.
            script: Internally constructed read-only JavaScript, supplied through stdin.

        Raises:
            CalledProcessError: SSH or the legacy database tool fails.
            OSError: A local tool or output file is unavailable.
        """
        if self.args.ssh_host:
            command = [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=15",
                "-o",
                "ServerAliveInterval=30",
                "-o",
                "ServerAliveCountMax=3",
                "--",
                self.args.ssh_host,
                shlex.join(command),
            ]
        with output.open("w") as stream, output.with_suffix(".stderr").open("w") as errors:
            subprocess.run(
                command, input=script, text=True, stdout=stream, stderr=errors, check=True
            )

    def shell(self, script: str, output: Path) -> None:
        """Execute an internally generated read-only script with the source's mongo shell.

        Args:
            script: ES5-compatible JavaScript for MongoDB 3.2.
            output: Protected local output file.
        """
        self.execute(
            [
                self.args.mongo_shell,
                "--quiet",
                "--host",
                self.args.mongo_host,
                "--port",
                str(self.args.mongo_port),
                self.database,
            ],
            output,
            script,
        )

    def snapshot(self, query: Document, output: Path) -> None:
        """Record the ordered selected sample IDs once without exporting clinical payloads.

        Args:
            query: Source-version assay predicate from the shared migration scope rules.
            output: JSON-lines file containing only BSON ObjectId wrappers.
        """
        self.shell(
            'db.getCollection("samples").find(' + json.dumps(query) + ", {_id:1})"
            ".sort({_id:1}).forEach(function(r) {"
            "print(JSON.stringify({_id:{$oid:r._id.valueOf()}}));});\n",
            output,
        )

    def discover(self, output: Path) -> list[str]:
        """Find physical collections with explicit sample-owner fields before batch export.

        Args:
            output: Protected inventory output; discovery runs once per export run.

        Returns:
            Sorted names, always including samples. Shared records without sample-owner
            fields are excluded. A timed-out collection scan fails instead of omitting data.
        """
        self.shell(
            'var names=["samples"]; db.getCollectionNames().sort().forEach(function(n) {'
            'if(n==="samples" || n.indexOf("system.")===0) return;'
            "var c=db.getCollection(n).find({$or:[{SAMPLE_ID:{$exists:true}},"
            "{sample_oid:{$exists:true}}]}, {_id:1}).limit(1).maxTimeMS("
            + str(self.args.discovery_timeout_ms)
            + ");"
            "if(c.hasNext()) names.push(n);}); print(JSON.stringify(names));\n",
            output,
        )
        names = json.loads(output.read_text())
        if (
            not isinstance(names, list)
            or "samples" not in names
            or any(
                not isinstance(name, str)
                or not name
                or "/" in name
                or "\\" in name
                or name in {".", ".."}
                or name.startswith("system.")
                for name in names
            )
        ):
            raise ValueError("Invalid source collection inventory")
        return sorted(set(names), key=lambda name: (name != "samples", name))

    def export(self, collection: str, ids: list[str], output: Path) -> None:
        """Export unchanged source documents with BSON-aware sample ownership predicates.

        Args:
            collection: Physical source collection, not a destination schema name.
            ids: At most 500 original sample ObjectIds in canonical textual form.
            output: Protected raw mongoexport JSON-lines file.
        """
        oid_values = [{"$oid": identity} for identity in ids]
        query = (
            {"_id": {"$in": oid_values}}
            if collection == "samples"
            else {
                "$or": [
                    {field: {"$in": [*ids, *(i.upper() for i in ids), *oid_values]}}
                    for field in OWNER_FIELDS
                ]
            }
        )
        self.execute(
            [
                self.args.mongoexport,
                "--host",
                self.args.mongo_host,
                "--port",
                str(self.args.mongo_port),
                "--db",
                self.database,
                "--collection",
                collection,
                "--query",
                json.dumps(query, separators=(",", ":")),
            ],
            output,
        )


def owner(document: Document) -> str:
    """Require one unambiguous scalar sample ObjectId across the recorded owner fields.

    Args:
        document: Related source document before any migration or normalization.

    Returns:
        Canonical textual sample ObjectId; strings and BSON ObjectIds are accepted.

    Raises:
        ValueError: Ownership is absent, malformed, an array or conflicting.
    """
    values = [document[field] for field in OWNER_FIELDS if document.get(field) is not None]
    if not values or any(
        not isinstance(v, (str, ObjectId)) or not ObjectId.is_valid(v) for v in values
    ):
        raise ValueError("Related record has missing, malformed or nonscalar sample ownership")
    owners = {str(ObjectId(v)) for v in values}
    if len(owners) != 1:
        raise ValueError("Related record has conflicting sample owners")
    return owners.pop()


def verify_file(directory: Path, filename: str, digest: str) -> Path:
    """Check a manifest's local data file before trusting its progress or exported IDs.

    Args:
        directory: Batch or export directory containing the checkpointed data file.
        filename: One plain file name from a checkpoint.
        digest: Expected SHA-256 of the file's exact bytes.

    Returns:
        Verified file path.

    Raises:
        ValueError: Path traversal, symlinks, missing files or changed bytes are detected.
    """
    path = directory / filename
    if Path(filename).name != filename or path.is_symlink() or not path.is_file():
        raise ValueError("Invalid checkpoint file path")
    if file_hash(path) != digest:
        raise ValueError("Export checksum mismatch; restore the original file before resuming")
    return path


def sample_chunks(path: Path, size: int) -> Iterator[list[str]]:
    """Yield the fixed sample selection in ordered chunks without a source query on resume.

    Args:
        path: Checksum-verified source sample ID snapshot.
        size: Samples per batch, from 1 through 500.

    Yields:
        Up to size distinct textual sample ObjectIds in strictly increasing order.

    Raises:
        ValueError: Snapshot IDs are not BSON ObjectIds or are duplicated/out of order.
    """
    chunk = []
    previous = ""
    for document in json_rows(path):
        identity = document.get("_id")
        if not isinstance(identity, ObjectId) or str(identity) <= previous:
            raise ValueError("Sample ID snapshot is malformed, duplicated or unordered")
        previous = str(identity)
        chunk.append(previous)
        if len(chunk) == size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def index_file(
    path: Path, collection: str, index_root: Path, output: Path | None = None
) -> tuple[int, int]:
    """Merge fingerprints on disk with bounded sorting memory, without a local database.

    Args:
        path: Verified export or canonical pending collection file.
        collection: Physical collection used as the identity namespace.
        index_root: Temporary local index directory reconstructed on each invocation.
        output: Destination for new records, or None to index an existing checkpoint.

    Returns:
        Counts of newly indexed and skipped identical records.

    Raises:
        ValueError: Identity is missing, duplicates conflict or a checkpoint repeats an ID.
        CalledProcessError: The local external sort fails.
    """
    ledger = index_root / (fingerprint(collection) + ".index")
    ledger.touch(exist_ok=True)
    count = 0
    skipped = 0
    with TemporaryDirectory(dir=index_root) as temporary:
        scratch = Path(temporary)
        metadata = scratch / "records.tsv"
        ordered = scratch / "sorted.tsv"
        next_index = scratch / "next.index"
        with path.open("rb") as stream, metadata.open("w") as meta:
            while True:
                offset = stream.tell()
                line = stream.readline()
                if not line:
                    break
                if not line.strip():
                    continue
                document = json_util.loads(line)
                if not isinstance(document, dict) or "_id" not in document:
                    raise ValueError("Source document has no identity")
                meta.write(f"{fingerprint(document['_id'])}\t{fingerprint(document)}\t{offset}\n")
        with (scratch / "sort.stderr").open("w") as errors:
            subprocess.run(
                [
                    "sort",
                    "-S",
                    "32M",
                    "-T",
                    str(scratch),
                    "-t",
                    "\t",
                    "-k1,1",
                    "-o",
                    str(ordered),
                    str(metadata),
                ],
                env={**os.environ, "LC_ALL": "C"},
                stderr=errors,
                check=True,
            )
        with (
            ledger.open() as old,
            ordered.open() as new,
            next_index.open("w") as target,
            path.open("rb") as data,
        ):
            old_line = old.readline()
            last_identity = ""
            last_digest = ""
            destination = output.open("wb") if output else None
            try:
                for line in new:
                    identity, digest, offset = line.rstrip("\n").split("\t")
                    while old_line and old_line.split("\t", 1)[0] < identity:
                        target.write(old_line)
                        old_line = old.readline()
                    previous = last_digest if last_identity == identity else None
                    if old_line and old_line.split("\t", 1)[0] == identity:
                        previous = old_line.rstrip("\n").split("\t")[1]
                    if previous is not None:
                        if previous != digest:
                            raise ValueError(
                                "Previously exported document changed; use a stable source snapshot"
                            )
                        if output is None:
                            raise ValueError("Duplicate identity in checkpointed exports")
                        skipped += 1
                        continue
                    target.write(f"{identity}\t{digest}\n")
                    last_identity, last_digest = identity, digest
                    count += 1
                    if destination:
                        data.seek(int(offset))
                        destination.write(data.readline())
                while old_line:
                    target.write(old_line)
                    old_line = old.readline()
            finally:
                if destination:
                    destination.close()
        next_index.replace(ledger)
    return count, skipped


def export_batch(
    source: Source,
    directory: Path,
    ids: list[str],
    collections: list[str],
    index_root: Path,
    scope: Document,
) -> Document:
    """Export or resume one batch, checkpointing each successfully verified collection.

    Args:
        source: Read-only legacy command adapter.
        directory: Numbered batch directory inside the protected export root.
        ids: Exact sample IDs assigned to this batch by the fixed snapshot.
        collections: Physical sample-owned collections discovered once at run start.
        index_root: Temporary disk ledger of previously checkpointed record identities.
        scope: Source version and selected assay for sample-scope verification.

    Returns:
        Completed batch manifest. Embedded comments, reports, QC and other source
        sample content remain intact; this function performs no schema conversion.

    Raises:
        ValueError: Scope, ownership, existing checkpoints, identities or content conflict.
        CalledProcessError: A read fails; earlier collection checkpoints remain resumable.
    """
    directory.mkdir(mode=0o700, exist_ok=True)
    progress = directory / "progress.json"
    state = (
        json.loads(progress.read_text())
        if progress.exists()
        else {
            "sample_ids": ids,
            "files": {},
            "complete": False,
        }
    )
    if state.get("sample_ids") != ids or set(state.get("files", {})) - set(collections):
        raise ValueError("Batch checkpoint does not match the fixed selection/inventory")
    if state.get("complete") and set(state["files"]) != set(collections):
        raise ValueError("Completed batch has missing collection checkpoints")
    selected = set(ids)
    for collection in collections:
        filename = f"{collection}.jsonl"
        if collection in state["files"]:
            entry = state["files"][collection]
            path = verify_file(directory, filename, entry["sha256"])
            if index_file(path, collection, index_root)[0] != entry["count"]:
                raise ValueError("Checkpoint record count mismatch")
            continue
        raw = directory / f"{collection}.raw.jsonl"
        source.export(collection, ids, raw)
        staged = directory / f"{collection}.pending.jsonl"
        found_samples = set()
        with staged.open("w") as stream:
            for document in json_rows(raw):
                if "_id" not in document:
                    raise ValueError("Source document has no identity")
                if collection == "samples":
                    if (
                        not isinstance(document["_id"], ObjectId)
                        or str(document["_id"]) not in selected
                    ):
                        raise ValueError("Exported sample was not in the batch selection")
                    if not matches_source(document, scope["assay_id"], scope["source_version"]):
                        raise ValueError("Sample assay changed after selection; review the source")
                    found_samples.add(str(document["_id"]))
                elif owner(document) not in selected:
                    raise ValueError("Exported related record does not belong to this batch")
                stream.write(
                    json_util.dumps(document, json_options=json_util.CANONICAL_JSON_OPTIONS) + "\n"
                )
        if collection == "samples" and found_samples != selected:
            raise ValueError("A selected sample disappeared before export")
        path = directory / filename
        count, skipped = index_file(staged, collection, index_root, output=path)
        state["files"][collection] = {
            "sha256": file_hash(path),
            "count": count,
            "duplicates_skipped": skipped,
        }
        write_json(progress, state)
        raw.unlink()
        staged.unlink()
    state["complete"] = True
    write_json(progress, state)
    return state


def prepare(args: argparse.Namespace, source: Source) -> Document:
    """Create or resume a fixed assay export under the caller's exclusive output lock.

    Args:
        args: Export CLI options, including explicit resume and source identity.
        source: Legacy read adapter; replaceable by a synthetic adapter in tests.

    Returns:
        Whole-export completion manifest, containing per-batch manifest checksums.

    Raises:
        ValueError: Source identity, snapshot, batch files or resume options conflict.
    """
    root = args.output
    request = {
        "source_version": args.source_version,
        "database": "coyote" if args.source_version == 2 else "coyote3",
        "assay_id": args.assay_id,
        "batch_size": args.batch_size,
        "ssh_host": args.ssh_host,
        "mongo_host": args.mongo_host,
        "mongo_port": args.mongo_port,
    }
    request_file = root / "request.json"
    if request_file.exists():
        if json.loads(request_file.read_text()) != request:
            raise ValueError("Resume must use exactly the same source, assay and batch size")
    else:
        if any(path.name != ".export.lock" for path in root.iterdir()):
            raise ValueError("Output directory has files without a matching export request")
        write_json(request_file, request)
    selection_file = root / "selection.json"
    completed = root / "manifest.json"
    if completed.exists():
        previous = json.loads(completed.read_text())
        if previous.get("complete") is not True or any(
            previous.get(key) != value for key, value in request.items()
        ):
            raise ValueError("Invalid completed export manifest")
        verify_file(root, "selection.json", previous["selection_sha256"])
        for batch, digest in previous["batches"].items():
            if not re.fullmatch(r"batch-\d{6,}", batch):
                raise ValueError("Invalid batch directory in completed manifest")
            verify_file(root / batch, "progress.json", digest)
    if selection_file.exists():
        selection = json.loads(selection_file.read_text())
        verify_file(root, "sample_ids.jsonl", selection["sample_ids_sha256"])
        verify_file(root, "inventory.json", selection["inventory_sha256"])
        inventory = json.loads((root / "inventory.json").read_text())
        if selection["collections"] != inventory:
            raise ValueError("Collection inventory changed")
    else:
        collections = source.discover(root / "inventory.json")
        # Save the canonical inventory even when the shell used a different order.
        (root / "inventory.json").write_text(json.dumps(collections) + "\n")
        snapshot = root / "sample_ids.pending.jsonl"
        source.snapshot(mongo_query(assay_query(args.assay_id, args.source_version)), snapshot)
        count = sum(len(chunk) for chunk in sample_chunks(snapshot, args.batch_size))
        if not count:
            raise ValueError("No source samples match the selected assay")
        snapshot.replace(root / "sample_ids.jsonl")
        selection = {
            "collections": collections,
            "sample_count": count,
            "sample_ids_sha256": file_hash(root / "sample_ids.jsonl"),
            "inventory_sha256": file_hash(root / "inventory.json"),
        }
        write_json(selection_file, selection)
    batches = {}
    count = 0
    with TemporaryDirectory(dir=root, prefix="export-index-") as temporary:
        for number, ids in enumerate(sample_chunks(root / "sample_ids.jsonl", args.batch_size), 1):
            directory = root / f"batch-{number:06d}"
            state = export_batch(
                source, directory, ids, selection["collections"], Path(temporary), request
            )
            batches[directory.name] = file_hash(directory / "progress.json")
            count += len(ids)
            print(
                f"[ok] batch {number}: {len(ids)} samples; {count}/{selection['sample_count']} verified"
            )
            if not state["complete"]:
                raise ValueError("Batch was not completed")
    if count != selection["sample_count"]:
        raise ValueError("Selected sample count changed")
    manifest = {
        "complete": True,
        **request,
        **selection,
        "batches": batches,
        "selection_sha256": file_hash(selection_file),
    }
    write_json(root / "manifest.json", manifest)
    failure = root / "failure.json"
    if failure.exists():
        failure.unlink()
    return manifest


def main() -> int:
    """Export one assay with a single-writer lock and private error diagnostics.

    Returns:
        Zero on completion; one for protected read/checkpoint errors. The only source
        commands are collection discovery, sample ID reads and mongoexport reads.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-version", type=int, choices=(2, 3), required=True)
    parser.add_argument("--assay-id", type=str.lower, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--ssh-host", help="SSH destination, for example operator@source-host")
    parser.add_argument("--mongo-host", default="127.0.0.1")
    parser.add_argument("--mongo-port", type=int, default=27017)
    parser.add_argument("--mongo-shell", default="mongo")
    parser.add_argument("--mongoexport", default="mongoexport")
    parser.add_argument("--discovery-timeout-ms", type=int, default=30000)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 500:
        parser.error("--batch-size must be between 1 and 500")
    if not 1 <= args.mongo_port <= 65535 or args.discovery_timeout_ms < 1:
        parser.error("Invalid MongoDB port or collection discovery timeout")
    if not args.assay_id.strip() or args.ssh_host is not None and args.ssh_host.startswith("-"):
        parser.error("Assay and SSH destination must be valid nonempty values")
    if args.output.exists() and not args.resume:
        parser.error("Output exists; use --resume to verify and continue the same export")
    if args.resume and not (args.output / "request.json").is_file():
        parser.error("--resume requires an existing export request")
    args.output.mkdir(mode=0o700, parents=True, exist_ok=args.resume)
    with (args.output / ".export.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("[failed] Another exporter is using this output directory")
            return 1
        try:
            prepare(args, Source(args))
            print("[ok] Export complete; source database unchanged")
            return 0
        except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError) as error:
            # Do not include CalledProcessError.command: query arguments contain sample IDs.
            write_json(args.output / "failure.json", {"error_type": type(error).__name__})
            print(
                f"[failed] {type(error).__name__}; inspect protected .stderr files and checkpoints"
            )
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
