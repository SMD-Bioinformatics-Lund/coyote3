"""Convert non-variant sample evidence from protected Extended JSON exports."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Callable, Iterator
from copy import deepcopy
from pathlib import Path
from random import SystemRandom
from tempfile import TemporaryDirectory
from typing import Any

from bson import ObjectId, json_util
from pydantic import ValidationError

from coyote3.domain.dna.variant_identity import build_simple_id_hash_from_simple_id, normalize_chrom
from migrations_scripts.common import (
    derived_id,
    fingerprint,
    inspect_shapes,
    normalize_scope,
    rename,
    validate,
)

Document = dict[str, Any]
FINDINGS = {
    "cnvs": "cnv",
    "fusions": "fusion",
    "translocations": "translocation",
    "variants": "small_variant",
}
COVERAGE_COLLECTIONS = {"coverage", "panel_cov", "group_coverage"}


def coverage_destination(source: Document) -> str:
    """Classify a coverage document by its stored content rather than collection name.

    Args:
        source: A document from a possibly mixed coverage collection.

    Returns:
        d4_coverage for gene/transcript measurements, d4_coverage_blacklist for
        group/region exclusions, or coverage for original interval measurements.

    Raises:
        ValueError: The shape is unknown or combines incompatible coverage kinds.
    """
    matches = []
    if isinstance(source.get("genes"), dict):
        matches.append("d4_coverage")
    if {"group", "gene", "region"} <= source.keys():
        matches.append("d4_coverage_blacklist")
    if {"chr", "start", "end", "avg_cov"} <= source.keys():
        matches.append("coverage")
    if len(matches) != 1:
        raise ValueError("Unknown or ambiguous coverage document shape")
    return matches[0]


def convert_coverage_blacklist(source: Document) -> Document:
    """Preserve a scope-level D4 exclusion using its actual collection contract.

    Args:
        source: Original group/gene/region exclusion with its BSON identity.

    Returns:
        Validated exclusion with lowercase group identity and retained gene/coordinate data.

    Raises:
        ValueError: The document is a measurement rather than an exclusion.
        ValidationError: Its exclusion scope or coordinates are incomplete.
    """
    if coverage_destination(source) != "d4_coverage_blacklist":
        raise ValueError("Only D4 coverage exclusions belong in the blacklist")
    record = deepcopy(source)
    if isinstance(record.get("group"), str):
        record["group"] = record["group"].lower()
    return validate("d4_coverage_blacklist", record)


def json_rows(path: Path) -> Iterator[Document]:
    """Stream one BSON-aware JSON object per nonblank line.

    Args:
        path: Protected mongoexport or converter-produced JSON-lines file.

    Yields:
        Decoded documents, preserving ObjectIds and BSON dates.

    Raises:
        ValueError: A line is not a JSON object.
        OSError: The export cannot be opened.
    """
    with path.open() as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json_util.loads(line)
            if not isinstance(row, dict):
                raise ValueError("Each export line must be a document")
            yield row


def file_hash(path: Path) -> str:
    """Hash a large file in bounded memory.

    Args:
        path: Existing export or generated artifact.

    Returns:
        SHA-256 digest of the exact bytes.
    """
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sample_bundle(path: Path, version: int) -> dict[str, Document]:
    """Load a completed sample bundle after verifying its version and file checksums.

    Args:
        path: Output of the matching fresh sample converter.
        version: Required legacy source version.

    Returns:
        Collection names mapped to documents indexed by textual ObjectId.

    Raises:
        ValueError: Completion, checksum, ownership or identity verification fails.
    """
    manifest = json.loads((path / "manifest.json").read_text())
    if manifest.get("complete") is not True or manifest.get("source_version") != version:
        raise ValueError("Use a completed sample bundle from the matching source version")
    checksums = manifest.get("sha256", {})
    if "samples.jsonl" not in checksums:
        raise ValueError("Sample bundle has no verified samples file")
    for name, digest in checksums.items():
        if Path(name).name != name or file_hash(path / name) != digest:
            raise ValueError("Sample bundle checksum or filename is invalid")
    result = {}
    for collection in ("samples", "reports", "sample_comments"):
        rows = (
            list(json_rows(path / f"{collection}.jsonl"))
            if f"{collection}.jsonl" in checksums
            else []
        )
        indexed = {str(row["_id"]): row for row in rows}
        if len(indexed) != len(rows):
            raise ValueError("Duplicate identity in sample bundle")
        result[collection] = indexed
    if not result["samples"]:
        raise ValueError("Sample bundle is empty")
    for collection in ("reports", "sample_comments"):
        if any(
            str(row.get("sample_oid")) not in result["samples"]
            for row in result[collection].values()
        ):
            raise ValueError("Sample bundle has an orphan historical record")
    return result


def supplement(source: Document, review: Document | None) -> Document:
    """Supply only explicitly reviewed missing fields, including nested array members.

    Args:
        source: Original record used to check the review digest.
        review: Optional source_sha256, reason and dotted fields mapping.

    Returns:
        A source copy with verified missing values supplied.

    Raises:
        ValueError: The review is stale, changes identity, or replaces recorded content.
    """
    document = deepcopy(source)
    if review is None:
        return document
    if review.get("source_sha256") != fingerprint(source) or not review.get("reason"):
        raise ValueError("Missing-field review requires the exact source digest and reason")
    for path, value in review.get("fields", {}).items():
        parts = path.split(".")
        if (
            not all(parts)
            or any(p.startswith("$") for p in parts)
            or parts[0] in {"_id", "SAMPLE_ID", "sample_oid"}
        ):
            raise ValueError("Review cannot change record or sample identity")
        parent = document
        for part in parts[:-1]:
            if isinstance(parent, list):
                parent = parent[int(part)]
            elif isinstance(parent, dict):
                if parent.get(part) is None:
                    parent[part] = {}
                parent = parent[part]
            else:
                raise ValueError("Review path crosses a scalar")
        key = int(parts[-1]) if isinstance(parent, list) else parts[-1]
        existing = parent[key] if isinstance(parent, list) else parent.get(key)
        if existing is not None and existing != value:
            raise ValueError("Review cannot overwrite a recorded value")
        parent[key] = deepcopy(value)
    return document


def owner_id(source: Document, *, reported_finding: bool = False) -> str | None:
    """Read an explicit original sample ObjectId without resolving display names.

    Args:
        source: Related record before mutation.
        reported_finding: Allow the report snapshot contract's sample_oid owner field.

    Returns:
        Canonical textual ObjectId, or None if no owner is recorded or resolvable.

    Raises:
        ValueError: Explicit owner fields conflict or are malformed.
    """
    primary = source.get("SAMPLE_ID")
    if primary is None and reported_finding:
        primary = source.get("sample_oid")
    if primary is None:
        return None
    explicit = [
        str(source[key]) for key in ("SAMPLE_ID", "sample_oid") if source.get(key) is not None
    ]
    if explicit:
        if any(not ObjectId.is_valid(value) for value in explicit):
            raise ValueError("Related record has malformed sample ownership")
        explicit = [str(ObjectId(value)) for value in explicit]
        if len(set(explicit)) != 1:
            raise ValueError("Related record has malformed or conflicting sample ownership")
        return str(ObjectId(explicit[0]))
    return None


def finding_comments(document: Document, parent: Document, destination: str) -> list[Document]:
    """Extract finding comments with original authors, timestamps and IDs.

    Args:
        document: Mutable finding copy with an optional comments array.
        parent: Prepared owning sample.
        destination: variants, cnvs, fusions or translocations.

    Returns:
        Validated finding_comments records referencing the preserved finding ID.

    Raises:
        ValueError: Embedded comments are malformed or ownership conflicts.
    """
    output = []
    entries = document.pop("comments", [])
    if not isinstance(entries, list):
        raise ValueError("Finding comments must be an array")
    for index, item in enumerate(entries):
        if not isinstance(item, dict):
            raise ValueError("Finding comment must be a document")
        record = deepcopy(item)
        for key, value in (
            ("sample_oid", parent["_id"]),
            ("finding_oid", document["_id"]),
            ("finding_type", FINDINGS[destination]),
        ):
            if record.get(key, value) != value:
                raise ValueError("Finding comment has conflicting ownership")
            record[key] = value
        record.setdefault("_id", derived_id(document["_id"], "finding_comments", str(index)))
        record.setdefault("sample_name", parent["name"])
        output.append(validate("finding_comments", record))
    return output


def cnv_fields(document: Document) -> None:
    """Map recorded interval/VCF CNV fields without calculating a new copy-number ratio.

    Args:
        document: Mutable v2/v3 CNV copy.

    Raises:
        ValueError: Required coordinates or a finite numeric log-ratio are unavailable.
    """
    info = document.get("INFO") or {}
    for field, value in {
        "chr": document.get("CHROM"),
        "start": document.get("POS"),
        "end": info.get("END"),
        "nprobes": info.get("PROBES"),
        "ratio": info.get("FOLD_CHANGE_LOG"),
        "type": info.get("SVTYPE"),
    }.items():
        if document.get(field) is None and value is not None:
            document[field] = value
    if document.get("size") is None and info.get("SVLEN") is not None:
        document["size"] = abs(int(info["SVLEN"]))
    if isinstance(document.get("chr"), (int, float)):
        document["chr"] = str(document["chr"])
    if "genes" not in document and isinstance(info.get("genes"), list):
        document["genes"] = [
            {"gene": gene} if isinstance(gene, str) else gene for gene in info["genes"]
        ]
    if document.get("ratio") is not None:
        ratio = float(document["ratio"])
        if not math.isfinite(ratio):
            raise ValueError("CNV ratio must be finite")
        document["ratio"] = ratio
    if "start" in document and "end" in document and int(document["start"]) > int(document["end"]):
        raise ValueError("CNV interval is reversed")


def translocation_fields(document: Document) -> None:
    """Normalize stored structural fields while leaving absent support/classification unknown.

    Args:
        document: Mutable original translocation record.

    Raises:
        ValueError: Old and current genotype sample fields conflict.
    """
    if isinstance(document.get("CHROM"), (int, float)):
        document["CHROM"] = str(document["CHROM"])
    if isinstance(document.get("FILTER"), str):
        document["FILTER"] = document["FILTER"].split(";")
    if document.get("QUAL") in (".", ""):
        document["QUAL"] = None
    info = document.get("INFO", {})
    if isinstance(info.get("PANEL"), str):
        info["PANEL"] = info["PANEL"].split("|")
    for genotype in document.get("GT", []):
        rename(genotype, "_sample_id", "sample")


def reported_fields(document: Document, parent: Document, context: dict[str, Document]) -> None:
    """Preserve saved report findings and verify their report/comment parents without reading variants.

    Args:
        document: Mutable source snapshot; no current annotation text is substituted.
        parent: Prepared sample with its original ObjectId.
        context: Verified reports and sample_comments from the sample bundle.

    Raises:
        ValueError: A report/comment parent or preserved identity hash conflicts.
    """
    report = context["reports"].get(str(document.get("report_oid")))
    if report is None or report["sample_oid"] != parent["_id"]:
        raise ValueError("Reported finding has no matching report in the sample bundle")
    if document.get("report_id", report["report_id"]) != report["report_id"]:
        raise ValueError("Reported finding report ID conflicts")
    document.setdefault("report_id", report["report_id"])
    document.setdefault("report_num", report["report_num"])
    document.setdefault("sample_name", parent["name"])
    comment_id = document.get("sample_comment_oid")
    if comment_id is not None:
        comment = context["sample_comments"].get(str(comment_id))
        if comment is None or comment["sample_oid"] != parent["_id"]:
            raise ValueError("Reported finding references an absent sample comment")
    if not document.get("simple_id"):
        raise ValueError("Preserved report finding identity is required")
    digest = build_simple_id_hash_from_simple_id(document["simple_id"])
    if document.get("simple_id_hash") not in (None, digest):
        raise ValueError("Reported finding identity hash conflicts")
    document["simple_id_hash"] = digest
    label = str(document.get("var_type") or "").upper()
    known = {
        "SNV": ("SNV", "small_variant"),
        "INDEL": ("SNV", "small_variant"),
        "CNV": ("CNV", "cnv"),
        "FUSION": ("FUSION", "fusion"),
        "TRANSLOCATION": ("TRANSLOCATION", "translocation"),
        "PGX": ("PGX", "pgx"),
        "HRD": ("HRD", "biomarker"),
        "MSI": ("MSI", "biomarker"),
        "TMB": ("TMB", "biomarker"),
    }
    if label in known:
        analysis, finding = known[label]
        if document.get("analysis_type", analysis) != analysis:
            raise ValueError("Reported finding analysis type conflicts with stored var_type")
        document.setdefault("analysis_type", analysis)
        document.setdefault("finding_type", finding)
        document["var_type"] = label
    normalize_scope(document)
    if isinstance(document.get("diagnosis"), str):
        scope = {"diagnosis_id": document["diagnosis"]}
        normalize_scope(
            scope, unspecified_diagnosis="legacy" if document.get("assay") == "tumwgs" else "base"
        )
        document["diagnosis"] = scope["diagnosis_id"]


def convert_record(
    source: Document,
    destination: str,
    parent: Document,
    context: dict[str, Document],
    review: Document | None = None,
) -> dict[str, list[Document]]:
    """Convert one explicitly owned non-variant record and any embedded finding comments.

    Args:
        source: Unmodified source record.
        destination: Current collection name, explicitly excluding variants and anno_vep.
        parent: Verified prepared sample with matching ownership.
        context: Prepared reports and sample_comments for saved-finding validation.
        review: Optional digest-bound missing-field additions.

    Returns:
        Current destination records and, for finding collections, extracted comments.

    Raises:
        ValueError: Scope, supported shape, measurements or related references conflict.
        ValidationError: Current collection contracts reject the converted record.
    """
    allowed = {
        "cnvs",
        "translocations",
        "fusions",
        "biomarkers",
        "pgx",
        "d4_coverage",
        "d4_coverage_blacklist",
        "coverage",
        "rna_expression",
        "rna_classification",
        "rna_qc",
        "reported_variants",
    }
    if destination not in allowed:
        raise ValueError("Only the declared non-variant related collections can be converted")
    if (
        destination in {"fusions", "rna_expression", "rna_qc", "rna_classification"}
        and parent.get("asp_category") != "rna"
    ):
        raise ValueError("RNA evidence requires an RNA sample")
    if (
        destination in {"cnvs", "translocations", "biomarkers", "d4_coverage"}
        and parent.get("asp_category") != "dna"
    ):
        raise ValueError("DNA evidence requires a DNA sample")
    document = supplement(source, review)
    normalize_scope(document)
    if not isinstance(document.get("_id"), ObjectId):
        raise ValueError("Original related record ObjectId is required")
    owner = (
        document.get("sample_oid")
        if destination == "reported_variants"
        else document.get("SAMPLE_ID")
    )
    if owner is None or str(owner) != str(parent["_id"]):
        raise ValueError("Related record belongs to a different sample")
    if destination == "reported_variants":
        document["sample_oid"] = parent["_id"]
        reported_fields(document, parent, context)
    else:
        document["SAMPLE_ID"] = str(parent["_id"])
    if destination == "cnvs":
        cnv_fields(document)
    elif destination == "translocations":
        translocation_fields(document)
    elif destination == "biomarkers":
        for key in ("MSIS", "MSIP"):
            if isinstance(document.get(key), dict):
                rename(document[key], "perc", "per")
        document.setdefault("name", parent["name"])
        if not any(
            isinstance(document.get(key), dict) and document[key]
            for key in ("HRD", "MSIS", "MSIP", "TMB")
        ):
            raise ValueError("A typed recorded biomarker measurement is required")
        if isinstance(document.get("TMB"), dict) and document["TMB"].get("unit") != "mut/Mb":
            raise ValueError("TMB requires an explicitly recorded mutations-per-megabase unit")
    elif destination == "d4_coverage":
        if not isinstance(document.get("genes"), dict) or not document["genes"]:
            raise ValueError("D4 coverage requires recorded gene/transcript structure")
        document.setdefault("sample", parent["name"])
    elif destination == "d4_coverage_blacklist":
        return {destination: [convert_coverage_blacklist(document)]}
    elif destination == "coverage":
        if coverage_destination(document) != "coverage":
            raise ValueError("Normal coverage must contain its original interval measurements")
        depth = float(document["avg_cov"])
        if not math.isfinite(depth) or depth < 0 or int(document["start"]) > int(document["end"]):
            raise ValueError("Invalid normal coverage interval or depth")
    comments = finding_comments(document, parent, destination) if destination in FINDINGS else []
    output = {
        destination: [document if destination == "coverage" else validate(destination, document)]
    }
    if comments:
        output["finding_comments"] = comments
    return output


def interval_coverage(rows: Iterator[Document], parent: Document, mapping: Document) -> Document:
    """Build one coverage document from recorded amplicon depths and a reviewed region map.

    Args:
        rows: One sample's intervals, streamed from protected staging storage.
        parent: Prepared sample retaining its original identity.
        mapping: Amplicon IDs mapped to gene, transcript, membership, region_kind and region_id.
            Optional nbr is an explicitly known exon number, never inferred from names.

    Returns:
        Validated d4_coverage with source interval IDs retained on each region.

    Raises:
        ValueError: Mapping, coordinates, depths or repeated regions are ambiguous.
    """
    if parent.get("asp_category") != "dna":
        raise ValueError("Interval coverage requires a DNA sample")
    genes: Document = {}
    for row in rows:
        if not isinstance(row.get("_id"), ObjectId):
            raise ValueError("Original coverage interval ObjectId is required")
        if row.get("SAMPLE_ID") is not None and str(row["SAMPLE_ID"]) != str(parent["_id"]):
            raise ValueError("Coverage interval belongs to a different sample")
        spec = mapping.get(row.get("amplicon"))
        if not isinstance(spec, dict):
            raise ValueError("Coverage interval needs a reviewed amplicon-to-region mapping")
        gene, region_id, kind = spec["gene"], spec["region_id"], spec["region_kind"]
        if kind not in {"exons", "CDS", "probes"}:
            raise ValueError("Coverage region_kind must be exons, CDS or probes")
        if normalize_chrom(spec["transcript"]["chr"]) != normalize_chrom(row["chr"]):
            raise ValueError("Coverage interval and mapped transcript chromosomes disagree")
        initial = {
            "covered_by_panel": spec["covered_by_panel"],
            "transcript": spec["transcript"],
            "exons": {},
            "CDS": {},
            "probes": {},
        }
        entry = genes.setdefault(gene, deepcopy(initial))
        if (
            entry["transcript"] != spec["transcript"]
            or entry["covered_by_panel"] != spec["covered_by_panel"]
        ):
            raise ValueError("Coverage map gives conflicting transcript or membership for one gene")
        if region_id in entry[kind]:
            raise ValueError("Duplicate coverage interval requires explicit reconciliation")
        value = float(row["avg_cov"])
        if not math.isfinite(value) or value < 0:
            raise ValueError("Coverage must be a finite nonnegative depth")
        region = {
            "chr": str(row["chr"]),
            "start": row["start"],
            "end": row["end"],
            "cov": value,
            "source_record_oid": row["_id"],
        }
        if int(region["start"]) > int(region["end"]):
            raise ValueError("Coverage interval is reversed")
        if kind != "probes" and "nbr" in spec:
            region["nbr"] = spec["nbr"]
        entry[kind][region_id] = region
    if not genes:
        raise ValueError("No intervals were supplied")
    return validate(
        "d4_coverage",
        {
            "_id": derived_id(parent["_id"], "d4_coverage", "coverage"),
            "SAMPLE_ID": str(parent["_id"]),
            "sample": parent["name"],
            "genes": genes,
        },
    )


def run(version: int, collections: dict[str, str], converter: Callable) -> int:
    """Inspect or prepare one non-variant source collection for a completed sample selection.

    Args:
        version: Source major version, used to verify the prepared sample bundle.
        collections: Explicit source-to-target mapping from the versioned entry point.
        converter: Version-specific record converter.

    Returns:
        Zero for completed inspection/preparation; one on a reported failure.
        No database connection or write is performed.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("inspect", "prepare"))
    parser.add_argument("--collection", required=True, choices=sorted(collections))
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--sample-bundle", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--coverage-map", type=Path)
    parser.add_argument(
        "--prior-bundle",
        action="append",
        type=Path,
        default=[],
        help="Check previously prepared related bundles for ID/coverage collisions",
    )
    parser.add_argument("--random-documents", type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.random_documents <= 100:
        parser.error("--random-documents must be between 1 and 100")
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    counts: Counter = Counter()
    output_counts: Counter = Counter()
    current: Document | None = None
    output_ids: dict[str, set[str]] = defaultdict(set)
    coverage_owners: set[str] = set()

    def write(name: str, row: Document) -> None:
        """Append a BSON-preserving local record without touching any database."""
        if name not in {"source_records", "sampled_source"}:
            identity = str(row["_id"])
            if identity in output_ids[name]:
                raise ValueError(
                    "Destination record identity is duplicated; reconcile source alternatives"
                )
            if name == "d4_coverage":
                if row["SAMPLE_ID"] in coverage_owners:
                    raise ValueError(
                        "Multiple coverage documents target the same sample; choose a source explicitly"
                    )
                coverage_owners.add(row["SAMPLE_ID"])
            output_ids[name].add(identity)
        with (args.output / f"{name}.jsonl").open("a") as stream:
            stream.write(json_util.dumps(row, json_options=json_util.CANONICAL_JSON_OPTIONS) + "\n")
        output_counts[name] += 1

    try:
        context = sample_bundle(args.sample_bundle, version)
        for prior in args.prior_bundle:
            manifest = json.loads((prior / "manifest.json").read_text())
            if manifest.get("complete") is not True or "output_counts" not in manifest:
                raise ValueError("Prior related bundle is incomplete or has the wrong format")
            for name in manifest["output_counts"]:
                if name == "source_records":
                    continue
                filename = f"{name}.jsonl"
                if Path(filename).name != filename or file_hash(prior / filename) != manifest[
                    "sha256"
                ].get(filename):
                    raise ValueError("Prior related bundle checksum is invalid")
                for row in json_rows(prior / filename):
                    output_ids[name].add(str(row["_id"]))
                    if name == "d4_coverage":
                        coverage_owners.add(row["SAMPLE_ID"])
        samples = context["samples"]
        reviews = json_util.loads(args.review.read_text()).get("records", {}) if args.review else {}
        mapping = json_util.loads(args.coverage_map.read_text()) if args.coverage_map else {}
        destination = collections[args.collection]
        seen: set[ObjectId] = set()
        reservoir: list[Document] = []
        random = SystemRandom()
        covered: set[str] = set()
        with TemporaryDirectory(dir=args.output, prefix="interval-staging-") as staging:
            for current in json_rows(args.input):
                counts["input"] += 1
                if (
                    args.collection in COVERAGE_COLLECTIONS
                    and {"group", "gene", "region"} <= current.keys()
                    and not isinstance(current.get("genes"), dict)
                    and not {"chr", "start", "end", "avg_cov"} <= current.keys()
                ):
                    counts["non_sample_exclusions"] += 1
                    continue
                raw_owner = current.get("SAMPLE_ID")
                if raw_owner is None and args.collection == "reported_variants":
                    raw_owner = current.get("sample_oid")
                if raw_owner is None or not ObjectId.is_valid(str(raw_owner)):
                    counts["unlinked"] += 1
                    continue
                owner = str(ObjectId(str(raw_owner)))
                if owner not in samples:
                    counts["outside_selection"] += 1
                    continue
                owner_id(current, reported_finding=args.collection == "reported_variants")
                counts["selected"] += 1
                if args.action == "inspect":
                    if len(reservoir) < args.random_documents:
                        reservoir.append(current)
                    else:
                        slot = random.randrange(counts["selected"])
                        if slot < args.random_documents:
                            reservoir[slot] = current
                    continue
                if not isinstance(current.get("_id"), ObjectId) or current["_id"] in seen:
                    raise ValueError("Source record identity is missing or duplicated")
                seen.add(current["_id"])
                write("source_records", current)
                if (
                    args.collection in COVERAGE_COLLECTIONS
                    and coverage_destination(current) == "coverage"
                    and mapping
                ):
                    with (Path(staging) / f"{owner}.jsonl").open("a") as stream:
                        stream.write(
                            json_util.dumps(current, json_options=json_util.CANONICAL_JSON_OPTIONS)
                            + "\n"
                        )
                    covered.add(owner)
                    continue
                review = reviews.get(str(current["_id"]))
                for name, rows in converter(
                    current, args.collection, samples[owner], context, review
                ).items():
                    for row in rows:
                        write(name, row)
            if args.action == "prepare":
                for owner in sorted(covered):
                    current = {"sample_oid": ObjectId(owner)}
                    write(
                        "d4_coverage",
                        interval_coverage(
                            json_rows(Path(staging) / f"{owner}.jsonl"), samples[owner], mapping
                        ),
                    )
        if args.action == "inspect":
            (args.output / "structure.json").write_text(
                json.dumps(
                    {"counts": dict(counts), "structure": inspect_shapes(reservoir)}, indent=2
                )
                + "\n"
            )
            for row in reservoir:
                write("sampled_source", row)
            (args.output / "review-template.json").write_text(
                json_util.dumps(
                    {
                        "records": {
                            str(row["_id"]): {
                                "source_sha256": fingerprint(row),
                                "reason": "",
                                "fields": {},
                            }
                            for row in reservoir
                        }
                    },
                    indent=2,
                )
                + "\n"
            )
        else:
            (args.output / "manifest.json").write_text(
                json.dumps(
                    {
                        "complete": True,
                        "source_version": version,
                        "source_collection": args.collection,
                        "destination": destination,
                        "sample_bundle_manifest_sha256": file_hash(
                            args.sample_bundle / "manifest.json"
                        ),
                        "source_sha256": file_hash(args.input),
                        "coverage_map_sha256": file_hash(args.coverage_map)
                        if args.coverage_map
                        else None,
                        "counts": dict(counts),
                        "output_counts": dict(output_counts),
                        "external_references": "Original var_oid and annotation IDs are preserved; validate them after their separate migrations.",
                        "sha256": {p.name: file_hash(p) for p in args.output.glob("*.jsonl")},
                    },
                    indent=2,
                )
                + "\n"
            )
        print(f"[ok] {args.action}: {counts['selected']} selected records; no database writes")
        return 0
    except (ValueError, OSError, KeyError, TypeError, IndexError) as error:
        details = (
            error.errors(include_input=False, include_context=False, include_url=False)
            if isinstance(error, ValidationError)
            else str(error)
        )
        (args.output / "failure.json").write_text(
            json_util.dumps(
                {
                    "error_type": type(error).__name__,
                    "record_id": current.get("_id") if current else None,
                    "details": details,
                },
                indent=2,
            )
            + "\n"
        )
        print(f"[failed] {type(error).__name__}; see protected failure.json. No database writes.")
        return 1


def run_blacklist(version: int) -> int:
    """Prepare scope-level coverage exclusions independently of sample-owned measurements.

    Args:
        version: Source version recorded in the output manifest.

    Returns:
        Zero on completion or one on a private validation failure. Only the explicitly
        selected group is converted; no sample linkage is inferred and no database is used.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--group", required=True, type=str.lower)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    counts: Counter = Counter()
    seen: set[ObjectId] = set()
    try:
        for source in json_rows(args.input):
            counts["input"] += 1
            if str(source.get("group", "")).lower() != args.group:
                counts["outside_group"] += 1
                continue
            if coverage_destination(source) != "d4_coverage_blacklist":
                counts["measurements"] += 1
                continue
            record = convert_coverage_blacklist(source)
            if record["_id"] in seen:
                raise ValueError("Duplicate coverage blacklist identity")
            seen.add(record["_id"])
            for name, row in (("d4_coverage_blacklist", record), ("source_records", source)):
                with (args.output / f"{name}.jsonl").open("a") as stream:
                    stream.write(
                        json_util.dumps(row, json_options=json_util.CANONICAL_JSON_OPTIONS) + "\n"
                    )
            counts["selected"] += 1
        (args.output / "manifest.json").write_text(
            json.dumps(
                {
                    "complete": True,
                    "source_version": version,
                    "group": args.group,
                    "destination": "d4_coverage_blacklist",
                    "counts": dict(counts),
                    "source_sha256": file_hash(args.input),
                    "sha256": {p.name: file_hash(p) for p in args.output.glob("*.jsonl")},
                },
                indent=2,
            )
            + "\n"
        )
        print(f"[ok] {counts['selected']} coverage exclusions prepared; no database writes")
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        details = (
            error.errors(include_input=False, include_context=False, include_url=False)
            if isinstance(error, ValidationError)
            else str(error)
        )
        (args.output / "failure.json").write_text(
            json_util.dumps(
                {
                    "error_type": type(error).__name__,
                    "details": details,
                },
                indent=2,
            )
            + "\n"
        )
        print(f"[failed] {type(error).__name__}; see protected failure.json. No database writes.")
        return 1
