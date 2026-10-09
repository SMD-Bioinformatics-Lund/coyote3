#!/usr/bin/env python3
"""Build contract-validated HGNC genes from reviewed HGNC TSV and Ensembl BioMart CSV files."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bson import BSON, json_util
from dotenv import dotenv_values
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.config.loaders.collections import load_collection_section  # noqa: E402
from api.config.mongo import mongo_endpoints  # noqa: E402
from api.contracts.schemas.reference import HgncGenesDoc  # noqa: E402
from api.infra.mongo.repositories.knowledgebase_publications import (  # noqa: E402
    record_reference_publication,
)
from api.infra.mongo.transactions import run_transaction  # noqa: E402

HGNC_FIELDS = {
    "hgnc_id": ("hgnc_id", str, None),
    "symbol": ("hgnc_symbol", str, None),
    "name": ("gene_name", str, None),
    "status": ("status", str, None),
    "location": ("locus", str, None),
    "location_sortable": ("locus_sortable", str, None),
    "alias_symbol": ("alias_symbol", str, "|"),
    "alias_name": ("alias_name", str, "|"),
    "prev_symbol": ("prev_symbol", str, "|"),
    "prev_name": ("prev_name", str, "|"),
    "date_approved_reserved": ("date_approved_reserved", datetime, None),
    "date_symbol_changed": ("date_symbol_changed", datetime, None),
    "date_name_changed": ("date_name_changed", datetime, None),
    "date_modified": ("date_modified", datetime, None),
    "entrez_id": ("entrez_id", int, None),
    "ensembl_gene_id": ("ensembl_gene_id", str, None),
    "refseq_accession": ("refseq_accession", str, "|"),
    "cosmic": ("cosmic", str, "|"),
    "omim_id": ("omim_id", int, "|"),
    "pseudogene.org": ("pseudogene_org", str, "|"),
    "imgt": ("imgt", str, None),
    "lncrnadb": ("lncrnadb", str, None),
    "lncipedia": ("lncipedia", str, None),
    "mane_select_ensembl": ("ensembl_mane_select", str, None),
    "mane_select_refseq": ("refseq_mane_select", str, None),
}
BIOMART_FIELDS = {
    "Chromosome/scaffold name": ("chromosome", str, None),
    "Gene start (bp)": ("start", int, None),
    "Gene end (bp)": ("end", int, None),
    "Strand": ("strand", int, None),
    "Transcript start (bp)": ("transcript_start", int, None),
    "Transcript end (bp)": ("transcript_end", int, None),
    "Transcript length (including UTRs and CDS)": ("transcript_length", int, None),
    "Gene type": ("gene_type", str, None),
    "HGNC ID": ("hgnc_id", str, None),
    "HGNC symbol": ("hgnc_symbol", str, None),
    "RefSeq match transcript (MANE Select)": ("refseq_mane_select", str, None),
    "RefSeq match transcript (MANE Plus Clinical)": ("refseq_mane_plus_clinical", str, "|"),
    "Gene description": ("gene_description", str, None),
    "Ensembl Canonical": ("ensembl_canonical", bool, None),
    "Transcription start site (TSS)": ("transcription_start_site", int, None),
    "Gene % GC content": ("gene_gc_content", float, None),
}


def convert(value: str, kind: type, separator: str | None) -> Any:
    """Parse source scalars or pipe lists without inventing values for missing numbers.

    Args:
        value: Source cell, with surrounding whitespace ignored.
        kind: Declared scalar type; dates accept ISO or day/month/year.
        separator: Pipe for list fields, or None for a scalar.

    Returns:
        Typed value; blank lists become empty, blank strings remain empty and other blanks null.

    Raises:
        ValueError: A nonblank cell is not a valid declared value.
    """
    value = value.strip()
    if separator:
        return sorted({kind(item.strip()) for item in value.split(separator) if item.strip()})
    if not value:
        return "" if kind is str else None
    if kind is bool:
        if value.lower() not in {"1", "0", "true", "false"}:
            raise ValueError("Canonical flag must be 1, 0, true or false")
        return value.lower() in {"1", "true"}
    if kind is datetime:
        for pattern in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(value, pattern).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        raise ValueError("Date must use YYYY-MM-DD or DD/MM/YYYY")
    return kind(value)


def read_rows(path: Path, fields: dict, delimiter: str, skip: int = 0) -> list[dict]:
    """Read mapped columns, rejecting duplicate headers, malformed rows and invalid cells.

    Args:
        path: Reviewed UTF-8 input file.
        fields: Source header to destination name/type/separator mapping.
        delimiter: Tab for HGNC or comma for BioMart.
        skip: Explicit number of metadata lines preceding the header.

    Returns:
        Typed rows; unmapped columns are ignored.

    Raises:
        ValueError: Headers, row widths or values are invalid.
    """
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for _ in range(skip):
            next(stream, None)
        reader = csv.DictReader(stream, delimiter=delimiter)
        headers = reader.fieldnames or []
        if not headers or len(headers) != len(set(headers)):
            raise ValueError(f"{path.name}: missing or duplicate headers")
        required = "hgnc_id" if delimiter == "\t" else "HGNC ID"
        if required not in headers:
            raise ValueError(f"{path.name}: missing {required} header")
        rows = []
        for row in reader:
            try:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError("Row width differs from header")
                rows.append(
                    {
                        target: convert(row[source], kind, separator)
                        for source, (target, kind, separator) in fields.items()
                        if source in row
                    }
                )
            except ValueError as exc:
                raise ValueError(f"{path.name}: line {reader.line_num + skip}: {exc}") from exc
    return rows


def build_genes(hgnc: list[dict], biomart: list[dict]) -> list[dict]:
    """Join reviewed rows by HGNC ID and validate every resulting gene before any write.

    Args:
        hgnc: Unique HGNC records with required contract fields.
        biomart: Matching transcript rows; all HGNC genes must have enrichment.

    Returns:
        Gene documents sorted by HGNC ID, including all provided MANE transcript bounds.

    Raises:
        ValueError: Identity, coordinates, transcript bounds or contract validation fails.
    """
    genes = {row["hgnc_id"]: row for row in hgnc}
    if not genes or "" in genes or len(genes) != len(hgnc):
        raise ValueError("HGNC input must contain unique, nonblank IDs and at least one gene")
    grouped: dict[str, list[dict]] = {}
    for row in biomart:
        identity = row.get("hgnc_id")
        if identity not in genes:
            raise ValueError(f"BioMart HGNC ID has no input gene: {identity!r}")
        grouped.setdefault(identity, []).append(row)
    documents = []
    for identity, gene in sorted(genes.items()):
        rows = grouped.get(identity, [])
        if not rows:
            raise ValueError(f"{identity}: missing BioMart enrichment")
        chromosomes = {row.get("chromosome") for row in rows}
        if (
            "" in chromosomes
            or None in chromosomes
            or (len(chromosomes) != 1 and chromosomes != {"X", "Y"})
        ):
            raise ValueError(f"{identity}: ambiguous or missing chromosome")
        primary = "X" if chromosomes == {"X", "Y"} else next(iter(chromosomes))
        selected = [row for row in rows if row["chromosome"] == primary]
        merged = dict(
            gene,
            _id=identity,
            chromosome=primary,
            other_chromosome="Y" if chromosomes == {"X", "Y"} else None,
        )
        for field in ("start", "end", "gene_gc_content", "gene_description"):
            values = {row.get(field) for row in selected}
            if len(values) != 1 or None in values:
                raise ValueError(f"{identity}: inconsistent or missing {field}")
            merged[field] = next(iter(values))
        if merged["start"] < 1 or merged["end"] < merged["start"]:
            raise ValueError(f"{identity}: invalid gene coordinates")
        if not 0 <= merged["gene_gc_content"] <= 100:
            raise ValueError(f"{identity}: invalid GC percentage")
        transcripts = {}
        for row in selected:
            if row.get("hgnc_symbol") != gene["hgnc_symbol"]:
                raise ValueError(f"{identity}: conflicting HGNC symbol")
            if row.get("ensembl_canonical") is None or not row.get("gene_type"):
                raise ValueError(f"{identity}: missing canonical flag or gene type")
            names = row.get("refseq_mane_plus_clinical", []) + (
                [row["refseq_mane_select"]] if row.get("refseq_mane_select") else []
            )
            for name in names:
                bounds = {
                    key: row.get(source)
                    for key, source in (
                        ("start", "transcript_start"),
                        ("end", "transcript_end"),
                        ("length", "transcript_length"),
                        ("start_site", "transcription_start_site"),
                    )
                }
                if any(value is None or value < 1 for value in bounds.values()) or (
                    bounds["end"] < bounds["start"]
                ):
                    raise ValueError(f"{identity}: invalid transcript bounds for {name}")
                if name in transcripts and transcripts[name] != bounds:
                    raise ValueError(f"{identity}: conflicting transcript bounds for {name}")
                transcripts[name] = bounds
        merged.update(
            gene_description=merged["gene_description"].split("[")[0].strip(),
            ensembl_canonical=any(row["ensembl_canonical"] for row in selected),
            gene_type=sorted({row["gene_type"] for row in selected}),
            refseq_mane_plus_clinical=sorted(
                {name for row in selected for name in row.get("refseq_mane_plus_clinical", [])}
            ),
            addtional_transcript_info=dict(sorted(transcripts.items())),
        )
        documents.append(HgncGenesDoc.model_validate(merged).model_dump())
    return documents


def install_genes(database: Any, documents: list[dict], backup: Path, provenance: dict) -> None:
    """Replace supplied genes atomically, preserving their IDs and all unrelated genes.

    Args:
        database: Configured knowledgebase database with maintenance write privileges.
        documents: Complete, contract-valid genes with unique HGNC identifiers.
        backup: New BSON file for original records; existing files are never overwritten.
        provenance: Reviewed release, assembly and source hashes recorded on each imported gene.

    Raises:
        ValueError: Input contracts or stored identities are inconsistent.
        RuntimeError: Target records changed after backup.
        FileExistsError: Backup already exists.

    Notes:
        Pause concurrent reference writers. Requires a replica set and never falls back
        to nontransactional writes. Does not change indexes, samples or stored reports.
    """
    validated = [HgncGenesDoc.model_validate(row).model_dump() for row in documents]
    ids = [row["hgnc_id"] for row in validated]
    if not ids or len(ids) != len(set(ids)) or any(not identity for identity in ids):
        raise ValueError("Gene installation requires unique nonblank HGNC identifiers")
    collection = database[load_collection_section("knowledgebase")["hgnc_collection"]]
    query = {"$or": [{"hgnc_id": {"$in": ids}}, {"_id": {"$in": ids}}]}
    original = list(collection.find(query))
    existing = {}
    for row in original:
        identity = row.get("hgnc_id")
        if (
            identity not in ids
            or identity in existing
            or (row["_id"] in ids and row["_id"] != identity)
        ):
            raise ValueError("Stored HGNC identities conflict; review before installation")
        existing[identity] = row
    descriptor = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        for row in original:
            stream.write(BSON.encode(row))

    def publish(session: Any) -> None:
        """Recheck the backup and publish genes and release activity in one transaction.

        Args:
            session: Session owned by the knowledgebase MongoClient.

        Raises:
            RuntimeError: The selected genes changed since backup.
        """
        current = list(collection.find(query, session=session))
        if sorted(current, key=lambda row: str(row["_id"])) != sorted(
            original, key=lambda row: str(row["_id"])
        ):
            raise RuntimeError("HGNC records changed after backup; use a new reviewed backup")
        for document in validated:
            row = dict(document)
            identity = row["hgnc_id"]
            row["_id"] = existing.get(identity, {}).get("_id", identity)
            row["import_provenance"] = provenance
            collection.replace_one({"_id": row["_id"]}, row, upsert=True, session=session)
        record_reference_publication(
            database, source="hgnc_genes", release=provenance["release"], session=session
        )

    run_transaction(database.client, publish)


def main() -> int:
    """Build a review artifact, optionally applying it to the configured knowledgebase.

    Returns:
        Zero after validation and any explicitly requested installation.

    Raises:
        ValueError: Source records or endpoint settings are invalid.
        FileExistsError: Output or backup paths already exist.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hgnc", required=True, type=Path)
    parser.add_argument("--biomart", required=True, type=Path)
    parser.add_argument("--hgnc-skip-lines", type=int, default=0)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--release", required=True)
    parser.add_argument("--assembly", required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    if args.hgnc_skip_lines < 0 or not args.release.strip() or not args.assembly.strip():
        parser.error("Skip count must be nonnegative; release and assembly must not be blank")
    if args.apply and not args.backup:
        parser.error("--apply requires --backup (a new BSON file)")
    documents = build_genes(
        read_rows(args.hgnc, HGNC_FIELDS, "\t", args.hgnc_skip_lines),
        read_rows(args.biomart, BIOMART_FIELDS, ","),
    )
    provenance = {
        "release": args.release,
        "assembly": args.assembly,
        "sha256": {
            key: hashlib.sha256(path.read_bytes()).hexdigest()
            for key, path in (("hgnc", args.hgnc), ("biomart", args.biomart))
        },
    }
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json_util.dumps({"provenance": provenance, "genes": documents}, indent=2))
        stream.write("\n")
    print(json.dumps({"validated_genes": len(documents), "applied": False}))
    if args.apply:
        config = {**(dotenv_values(args.env_file) if args.env_file else {}), **os.environ}
        endpoint = mongo_endpoints(config)["knowledgebase"]
        with MongoClient(endpoint.uri, serverSelectionTimeoutMS=10000) as client:
            install_genes(client[endpoint.database], documents, args.backup, provenance)
        print(json.dumps({"applied_genes": len(documents)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
