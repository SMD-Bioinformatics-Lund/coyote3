"""Build and query offline VEP evidence without connecting to legacy databases."""

from __future__ import annotations

import hashlib
import os
import sqlite3
from collections import Counter
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from bson import BSON, ObjectId

from coyote3.application.ingest.parsers import _build_anno_vep_docs
from coyote3.contracts.schemas.dna import VariantCsqDoc
from coyote3.contracts.schemas.variant_annotations import VepAnnoTranscriptDoc
from coyote3.domain.dna.variant_identity import (
    build_simple_id,
    build_simple_id_hash_from_simple_id,
    normalize_simple_id,
)
from scripts.migration_common.offline import (
    RecordConversionError,
    SourceIndex,
    digest,
    private_json,
    read_json,
    write_bundle,
)
from scripts.upgrade_from_v3.clinical_documents import validate_document


def normalize_csq(source: dict) -> dict:
    """Convert numeric VEP labels to text without selecting a transcript.

    Args:
        source: Original consequence; numeric fields declared as VEP labels become text.

    Returns:
        A copy preserving consequence terms and all additional source fields.
    """
    result = deepcopy(source)
    for key in VariantCsqDoc.model_fields:
        if key not in {"Consequence", "CLIN_SIG"} and key in result:
            if isinstance(result[key], (int, float)) and not isinstance(result[key], bool):
                result[key] = str(result[key])
    return result


def _hgvs(value: Any) -> str | None:
    """Read the HGVS expression independently of its optional accession prefix."""
    text = unquote(str(value or "")).strip()
    return text.split(":", 1)[-1] if text and text != "." else None


def variant_evidence(source: dict, version: str) -> dict:
    """Build versioned evidence from original consequences without selecting a call.

    Args:
        source: Original v2 or v3 small variant, including coordinates and INFO.CSQ.
        version: Explicit, historically evidenced VEP release for this record.

    Returns:
        Contract-valid vault record with a deterministic identity.

    Raises:
        ValueError: Coordinates, identity hashes, or consequence evidence conflict.
    """
    coordinates = [source.get(key) for key in ("CHROM", "POS", "REF", "ALT")]
    if any(value in (None, "") for value in coordinates):
        raise ValueError("VEP evidence requires complete original variant coordinates")
    simple_id = build_simple_id(*coordinates)
    if source.get("simple_id") and normalize_simple_id(source["simple_id"]) != simple_id:
        raise ValueError("VEP coordinates conflict with the recorded genomic identity")
    identity = build_simple_id_hash_from_simple_id(simple_id)
    if source.get("simple_id_hash") not in (None, identity):
        raise ValueError("VEP genomic identity hash conflicts")
    info = source.get("INFO") or {}
    consequences = info.get("CSQ")
    if not isinstance(consequences, list) or not consequences:
        raise ValueError("VEP evidence requires original transcript consequences")
    normalized = []
    for consequence in consequences:
        if not isinstance(consequence, dict):
            raise ValueError("VEP consequences must contain documents")
        normalized.append(
            VepAnnoTranscriptDoc.model_validate(normalize_csq(consequence)).model_dump(
                mode="python", exclude_unset=True
            )
        )
    selected = info.get("selected_CSQ")
    if isinstance(selected, dict):
        normalized.append(
            VepAnnoTranscriptDoc.model_validate(normalize_csq(selected)).model_dump(
                mode="python", exclude_unset=True
            )
        )
    normalized = _merge_evidence({"CSQ": [], "variant_class": None}, {"CSQ": normalized})["CSQ"]
    variant = {
        "simple_id": simple_id,
        "variant_class": source.get("variant_class") or consequences[0].get("VARIANT_CLASS"),
        "INFO": {"CSQ": normalized},
    }
    record = _build_anno_vep_docs([variant], version)[0]
    record["_id"] = ObjectId(digest((identity, version))[:24])
    return validate_document("anno_vep", record)


def _merge_evidence(existing: dict, incoming: dict) -> dict:
    """Union compatible transcript evidence and reject contradictory recorded values.

    Args:
        existing: Vault record already stored for this genomic identity and release.
        incoming: Additional source evidence for the same identity and release.

    Returns:
        Copied evidence with compatible missing fields filled and transcripts retained.

    Raises:
        ValueError: Both sources record different nonblank classes or transcript fields.
    """
    merged = deepcopy(existing)
    old_class, new_class = existing.get("variant_class"), incoming.get("variant_class")
    if old_class and new_class and old_class != new_class:
        raise ValueError("VEP variant classes conflict for one genomic identity/release")
    merged["variant_class"] = old_class or new_class
    transcripts = {}
    for row in [*existing["CSQ"], *incoming["CSQ"]]:
        key = row.get("Feature") or digest(row)
        if key not in transcripts:
            transcripts[key] = deepcopy(row)
            continue
        current = transcripts[key]
        for field, value in row.items():
            previous = current.get(field)
            if previous in (None, "", "."):
                current[field] = value
            elif value not in (None, "", ".") and previous != value:
                raise ValueError("VEP consequences conflict for the same transcript/release")
    merged["CSQ"] = [transcripts[key] for key in sorted(transcripts)]
    return merged


def build_vep_reference(
    sources: list[tuple[SourceIndex, dict]],
    output: Path,
    *,
    version: str,
    target_sha256: str,
    batch_size: int = 1000,
    references: dict | None = None,
) -> dict:
    """Stream complete source indexes into a shared disk-backed VEP reference.

    Args:
        sources: Read-only source indexes paired with their reviewed release evidence.
            ``vep_release`` supplies a digest-bound whole-export declaration; otherwise
            each variant must have recorded or per-sample reviewed release provenance.
        output: New private directory for the index, manifest, and bounded apply bundles.
        version: Release to retain, for example ``103``. Known other releases are counted.
        target_sha256: Validated destination catalog fingerprint used by apply bundles.
        batch_size: Maximum records per destination bundle, from 1 through 10000.
        references: Optional verified HGNC/VEP preflight to retain in bundle provenance.

    Returns:
        Completion manifest with source fingerprints, counts and evidence checksum.

    Raises:
        ValueError: Release provenance, genomic identity, or transcript evidence conflicts.
        RecordConversionError: A source variant requires private reconciliation.
        FileExistsError: The output already exists.
    """
    if not version.isdigit() or not 1 <= batch_size <= 10000 or not sources or not target_sha256:
        raise ValueError(
            "Explicit VEP version, source indexes, target catalog and batch size required"
        )
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    path = output / "anno_vep.sqlite"
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    stats = Counter(
        source_variants=0,
        other_release_variants=0,
        repeated_variants=0,
        unique_variants=0,
        bundles=0,
    )
    source_stamps = []
    assemblies: set[str] = set()
    with sqlite3.connect(path) as connection:
        connection.executescript(
            "CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT);"
            "INSERT INTO metadata VALUES ('complete','0');"
            "CREATE TABLE records (identity TEXT PRIMARY KEY, payload BLOB NOT NULL);"
            "CREATE TABLE identities (nomenclature TEXT, gene TEXT, transcript TEXT, "
            "variant TEXT, identity TEXT, PRIMARY KEY "
            "(nomenclature,gene,transcript,variant,identity));"
        )
        for source, review in sources:
            source_hash = source.fingerprint()
            source_stamps.append(
                {
                    "version": source.version,
                    "source_sha256": source_hash,
                    "review_sha256": digest(review),
                }
            )
            declaration = review.get("vep_release", {})
            if declaration and (
                declaration.get("source_sha256") != source_hash
                or not declaration.get("evidence")
                or not str(declaration.get("version", "")).isdigit()
            ):
                raise ValueError(
                    "Whole-export VEP release requires matching source digest and evidence"
                )

            @lru_cache(maxsize=1024)
            def sample_release(identity: str) -> tuple[set[str], set[str]]:
                """Read recorded/reviewed release and assembly for a source sample."""
                sample = source.get("samples", identity)
                item = review.get("samples", {}).get(identity, {}).get("sample", {})
                values = [
                    sample.get("vep_version"),
                    sample.get("database_versions", {}).get("vep"),
                    item.get("metadata", {}).get("database_versions", {}).get("vep"),
                ]
                builds = [
                    sample.get("genome_build"),
                    item.get("metadata", {}).get("genome_build"),
                    declaration.get("genome_build"),
                ]
                return (
                    {str(value).lstrip("vV") for value in values if value not in (None, "")},
                    {str(value) for value in builds if value not in (None, "")},
                )

            physical = "variants" if source.version == 3 else "variants_idref"
            for original in source.rows(physical):
                try:
                    releases, builds = sample_release(str(original["SAMPLE_ID"]))
                    releases = set(releases)
                    for value in (original.get("vep_version"), declaration.get("version")):
                        if value not in (None, ""):
                            releases.add(str(value).lstrip("vV"))
                    if len(releases) != 1:
                        raise ValueError("Original VEP release is absent or conflicting")
                    release = next(iter(releases))
                    stats["source_variants"] += 1
                    if release != version:
                        stats["other_release_variants"] += 1
                        continue
                    if len(builds) != 1:
                        raise ValueError(
                            "VEP reference requires one recorded or reviewed genome build"
                        )
                    assemblies.update(builds)
                    if len(assemblies) != 1:
                        raise ValueError("One VEP reference cannot mix genome builds")
                    record = variant_evidence(original, version)
                    identity = record["simple_id_hash"]
                    old = connection.execute(
                        "SELECT payload FROM records WHERE identity=?", (identity,)
                    ).fetchone()
                    if old:
                        record = _merge_evidence(BSON(old[0]).decode(), record)
                        stats["repeated_variants"] += 1
                    connection.execute(
                        "INSERT INTO records VALUES (?,?) ON CONFLICT(identity) "
                        "DO UPDATE SET payload=excluded.payload",
                        (identity, BSON.encode(record)),
                    )
                    if stats["source_variants"] % 1000 == 0:
                        connection.commit()
                except (ValueError, TypeError, KeyError) as error:
                    raise RecordConversionError(physical, original, error) from error
        checksum = hashlib.sha256()
        bundles = output / "bundles"
        bundles.mkdir(mode=0o700)
        chunk = []
        provenance = {
            "operation": "anno_vep",
            "source_version": source_stamps[0]["version"]
            if len({item["version"] for item in source_stamps}) == 1
            else "combined",
            "source_versions": sorted({item["version"] for item in source_stamps}),
            "sources": source_stamps,
            "references": references,
            "vep_version": version,
            "genome_build": next(iter(assemblies), None),
            "target_sha256": target_sha256,
        }
        for identity, payload in connection.execute(
            "SELECT identity,payload FROM records ORDER BY identity"
        ):
            record = BSON(payload).decode()
            checksum.update(payload)
            stats["unique_variants"] += 1
            for row in record["CSQ"]:
                gene, transcript = row.get("SYMBOL"), row.get("Feature")
                if not gene or not transcript:
                    continue
                for nomenclature, value in (
                    ("p", _hgvs(row.get("HGVSp"))),
                    ("c", _hgvs(row.get("HGVSc"))),
                    ("g", record["simple_id"]),
                ):
                    if value:
                        connection.execute(
                            "INSERT OR IGNORE INTO identities VALUES (?,?,?,?,?)",
                            (nomenclature, gene, transcript, value, identity),
                        )
            chunk.append(record)
            if len(chunk) == batch_size:
                stats["bundles"] += 1
                write_bundle(
                    bundles / f"{stats['bundles']:06d}", {"anno_vep": chunk}, provenance=provenance
                )
                chunk = []
        if chunk:
            stats["bundles"] += 1
            write_bundle(
                bundles / f"{stats['bundles']:06d}", {"anno_vep": chunk}, provenance=provenance
            )
        manifest = {
            "format": 1,
            **provenance,
            "counts": dict(stats),
            "records_sha256": checksum.hexdigest(),
        }
        connection.execute("INSERT INTO metadata VALUES ('version',?)", (version,))
        connection.execute("INSERT INTO metadata VALUES ('fingerprint',?)", (digest(manifest),))
        connection.execute("UPDATE metadata SET value='1' WHERE key='complete'")
    private_json(output / "manifest.json", manifest)
    return manifest


class VepReference:
    """Read a completed private VEP reference with exact transcript/version matching."""

    def __init__(self, directory: Path):
        """Open a completed index read-only and check its completion fingerprint.

        Args:
            directory: Private output directory from build_anno_vep.py.

        Raises:
            ValueError: The reference is incomplete or its manifest changed.
            OSError: A required reference artifact cannot be read.
        """
        self.connection = sqlite3.connect(
            (directory / "anno_vep.sqlite").resolve().as_uri() + "?mode=ro", uri=True
        )
        try:
            metadata = dict(self.connection.execute("SELECT key,value FROM metadata"))
            manifest = read_json(directory / "manifest.json")
            if metadata.get("complete") != "1" or metadata.get("fingerprint") != digest(manifest):
                raise ValueError("VEP reference is incomplete or its manifest changed")
            self.version = metadata["version"]
            self.fingerprint = metadata["fingerprint"]
            self.sources = manifest["sources"]
            self.references = manifest.get("references")
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        """Release the read-only reference connection."""
        self.connection.close()

    def record(self, identity: str) -> dict:
        """Read one genomic identity from the selected release.

        Args:
            identity: Canonical simple_id_hash, not a genomic string or source ObjectId.

        Returns:
            Original decoded vault evidence for this reference's selected release.

        Raises:
            ValueError: The hash has no record in the selected reference.
        """
        row = self.connection.execute(
            "SELECT payload FROM records WHERE identity=?", (identity,)
        ).fetchone()
        if row is None:
            raise ValueError("Variant is absent from the reviewed VEP reference")
        return BSON(row[0]).decode()

    def enrich(self, annotation: dict) -> dict:
        """Resolve complementary identities only for one exact historical transcript.

        Args:
            annotation: Scoped source annotation. Non-small-variant nomenclatures pass
                through unchanged. Small variants require gene, full transcript and identity.

        Returns:
            A copy carrying uniquely resolved genomic, coding and protein identities.

        Raises:
            ValueError: A transcript is absent, version-mismatched, ambiguous or conflicting.
        """
        result = deepcopy(annotation)
        kind = result.get("nomenclature")
        if kind not in {"p", "c", "g"}:
            return result
        rows = self.connection.execute(
            "SELECT identity FROM identities WHERE nomenclature=? AND gene=? AND transcript=? AND variant=?",
            (kind, result.get("gene"), result.get("transcript"), _hgvs(result.get("variant"))),
        ).fetchall()
        if len(rows) != 1:
            raise ValueError(
                "Annotation has no unique exact transcript/variant match in the VEP reference"
            )
        record = self.record(rows[0][0])
        consequences = [
            row
            for row in record["CSQ"]
            if row.get("Feature") == result.get("transcript")
            and row.get("SYMBOL") == result.get("gene")
        ]
        if len(consequences) != 1:
            raise ValueError("VEP transcript evidence is ambiguous")
        row = consequences[0]
        fields = {
            "hgvsp": _hgvs(row.get("HGVSp")),
            "hgvsc": _hgvs(row.get("HGVSc")),
            "genomic": record["simple_id"],
            "genomic_hash": record["simple_id_hash"],
        }
        for field, value in fields.items():
            if result.get(field) not in (None, value):
                raise ValueError("Recorded annotation identity conflicts with VEP evidence")
            result[field] = value
        return result
