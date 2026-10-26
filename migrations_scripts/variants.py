"""Prepare sample-owned variants, immutable VEP evidence and finding comments offline."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from bson import ObjectId, json_util
from pydantic import ValidationError

from coyote3.application.ingest.parsers import _parse_transcripts, _select_csq
from coyote3.contracts.schemas.dna import VariantCsqDoc
from coyote3.contracts.schemas.normalizers import normalize_ampersand_terms
from coyote3.contracts.schemas.variant_annotations import VepAnnoTranscriptDoc
from coyote3.domain.dna.transcript_payloads import build_hgnc_lookup_maps
from coyote3.domain.dna.variant_identity import (
    build_simple_id,
    build_simple_id_hash_from_simple_id,
    normalize_simple_id,
)
from migrations_scripts.common import derived_id, fingerprint, validate
from migrations_scripts.related import (
    file_hash,
    finding_comments,
    json_rows,
    owner_id,
    sample_bundle,
    supplement,
)

Document = dict[str, Any]
SOURCE_VEP_VERSION = "103"


def population_frequencies(csq: list[Document], allele: str) -> Document:
    """Extract recorded population frequencies, preserving missing values as null.

    Args:
        csq: Full transcript evidence before removal from the finding.
        allele: Alternate allele used to match historical ALLELE:FREQ entries.

    Returns:
        Maximum recorded frequency for each supported population field. No observation
        yields null rather than an invented zero. Existing finding values take precedence.

    Raises:
        ValueError: A recorded frequency is malformed, nonfinite or outside zero to one.
    """
    output = {}
    for target, keys in {
        "gnomad_frequency": ("gnomAD_AF", "gnomADg_AF"),
        "gnomad_max": ("MAX_AF",),
        "exac_frequency": ("ExAC_MAF",),
        "thousandG_frequency": ("GMAF",),
    }.items():
        values = []
        for row in csq:
            for key in keys:
                for item in str(row.get(key) if row.get(key) is not None else "").split("&"):
                    if ":" in item:
                        recorded_allele, item = item.rsplit(":", 1)
                        if recorded_allele.upper() != allele.upper():
                            continue
                    if item.strip() in {"", ".", "NA", "N/A"}:
                        continue
                    value = float(item)
                    if not math.isfinite(value) or not 0 <= value <= 1:
                        raise ValueError("Invalid recorded population frequency")
                    values.append(value)
        output[target] = max(values) if values else None
    return output


def transcript(source: Document) -> Document:
    """Normalize schema-defined transcript scalar types while preserving all VEP columns.

    Args:
        source: One raw consequence, including historical reference fields.

    Returns:
        A validated vault transcript with ampersand terms split and numeric HGNC IDs
        and strand values expressed as text. No transcript or gene is reselected.
    """
    row = deepcopy(source)
    for key in VepAnnoTranscriptDoc.model_fields:
        if key not in {"Consequence", "CLIN_SIG"} and isinstance(row.get(key), (int, float)):
            row[key] = str(row[key])
    if isinstance(row.get("STRAND"), (int, float)):
        row["STRAND"] = str(row["STRAND"])
    return VepAnnoTranscriptDoc.model_validate(row).model_dump(exclude_unset=True)


def convert(
    source: Document,
    sample: Document,
    *,
    review: Document | None = None,
    hgnc: tuple[dict[str, Document], dict[str, Document]] | None = None,
) -> dict[str, list[Document]]:
    """Separate a finding from its VEP transcripts without replacing recorded selection.

    Args:
        source: Original finding with BSON identity and explicit SAMPLE_ID.
        sample: Prepared owning sample with the same original ObjectId.
        review: Optional digest-bound missing fields, as supported by supplement.
        hgnc: Current HGNC lookup maps; explicitly enables application transcript
            selection only when the source has no selected_CSQ.

    Returns:
        Validated variants, anno_vep and extracted finding_comments records. All source
        transcript columns are retained in the vault, including the selected row.

    Raises:
        ValueError: Ownership, identity, selected transcript or VEP release is ambiguous.
        ValidationError: Current collection contracts reject the evidence.
    """
    if owner_id(source) != str(sample["_id"]):
        raise ValueError("Variant must reference its prepared sample by SAMPLE_ID")
    row = supplement(source, review)
    versions = {
        str(value).strip().lstrip("vV")
        for value in (
            row.get("vep_version"),
            sample.get("database_versions", {}).get("vep"),
            SOURCE_VEP_VERSION,
        )
        if value is not None and str(value).strip()
    }
    if len(versions) != 1:
        raise ValueError("Recorded VEP releases must agree with the confirmed source release 103")
    version = versions.pop()
    if not version:
        raise ValueError("VEP release must not be empty")
    simple_id = build_simple_id(row["CHROM"], row["POS"], row["REF"], row["ALT"])
    if row.get("simple_id") and normalize_simple_id(row["simple_id"]) != simple_id:
        raise ValueError("Recorded simple_id conflicts with variant coordinates")
    identity_hash = build_simple_id_hash_from_simple_id(simple_id)
    if row.get("simple_id_hash") and row["simple_id_hash"] != identity_hash:
        raise ValueError("Recorded variant hash conflicts with canonical identity")
    row.update(simple_id=simple_id, simple_id_hash=identity_hash)
    row["CHROM"] = str(row["CHROM"])
    row["SAMPLE_ID"] = str(sample["_id"])
    if isinstance(row.get("FILTER"), str):
        row["FILTER"] = [value for value in row["FILTER"].split(";") if value]
    info = row["INFO"]
    raw = info.pop("CSQ", [])
    if not isinstance(raw, list) or any(not isinstance(item, dict) for item in raw):
        raise ValueError("INFO.CSQ must contain transcript documents")
    csq = [transcript(item) for item in raw]
    selected = info.get("selected_CSQ")
    if not selected:
        if hgnc is None or not csq:
            raise ValueError(
                "Missing selected CSQ requires reviewed fields or --select-missing-csq"
            )
        by_id, by_symbol = hgnc
        selected, criterion = _select_csq(csq, by_id, by_symbol)
        info["selected_CSQ_criteria"] = criterion
    selected = transcript(selected)
    if not selected.get("Feature") or not info.get("selected_CSQ_criteria"):
        raise ValueError("Selected Feature and selection criterion must be recorded")
    if row.get("selected_csq_feature") not in (None, "", selected["Feature"]):
        raise ValueError("Recorded selected feature disagrees with selected CSQ")
    info["selected_CSQ"] = VariantCsqDoc.model_validate(selected).model_dump(exclude_unset=True)
    row["selected_csq_feature"] = selected["Feature"]
    # Equality includes every retained field: a slim selected row never replaces a richer row.
    csq = list({fingerprint(item): item for item in [*csq, selected]}.values())
    for key, value in population_frequencies(csq, row["ALT"]).items():
        if row.get(key) in (None, "", " ", "NA", "N/A"):
            row[key] = value
    aggregates = _parse_transcripts(csq)
    for key, value in zip(
        (
            "cosmic_ids",
            "dbsnp_id",
            "pubmed_ids",
            "transcripts",
            "HGVSc",
            "HGVSp",
            "genes",
            "hotspots",
            "consequence_terms",
        ),
        aggregates[1:],
        strict=True,
    ):
        if key == "consequence_terms":
            row[key] = list(dict.fromkeys([*normalize_ampersand_terms(row.get(key)), *value]))
        elif row.get(key) is None:
            row[key] = [value] if key == "hotspots" else value
    if row.get("variant_class") is None:
        row["variant_class"] = selected.get("VARIANT_CLASS")
    comments = finding_comments(row, sample, "variants")
    vault = validate(
        "anno_vep",
        {
            "_id": derived_id(ObjectId(identity_hash[:24]), "anno_vep", version),
            "simple_id": simple_id,
            "simple_id_hash": identity_hash,
            "vep_version": version,
            "variant_class": row.get("variant_class"),
            "CSQ": csq,
        },
    )
    # The original export is archived separately; the live variant holds no full CSQ array.
    if "CSQ" in row:
        raise ValueError("Unexpected top-level CSQ; review the source annotation location")
    return {
        "variants": [validate("variants", row)],
        "anno_vep": [vault],
        "finding_comments": comments,
    }


def merge_vault(existing: Document, incoming: Document) -> Document:
    """Union complete transcript rows for one allele/release without overwriting evidence.

    Args:
        existing: Previously validated vault row, possibly from an earlier bundle.
        incoming: Additional sample evidence for the same allele and VEP release.

    Returns:
        Validated union, retaining distinct rows even when their Feature is identical.

    Raises:
        ValueError: Allele, release, record ID or nonempty variant classes conflict.
    """
    for key in ("_id", "simple_id", "simple_id_hash", "vep_version"):
        if existing[key] != incoming[key]:
            raise ValueError("VEP vault identity conflict")
    classes = {r.get("variant_class") for r in (existing, incoming)} - {None, ""}
    if len(classes) > 1:
        raise ValueError("Conflicting VEP variant classes require review")
    result = deepcopy(existing)
    result["variant_class"] = next(iter(classes), None)
    result["CSQ"] = list({fingerprint(r): r for r in [*existing["CSQ"], *incoming["CSQ"]]}.values())
    return validate("anno_vep", result)


def run(version: int) -> int:
    """Prepare one version-specific export using an already verified sample selection.

    Args:
        version: Source major version, either 2 or 3.

    Returns:
        Zero after writing a complete local bundle, one on a protected validation failure.
        No database connection is created. Vault staging uses local BSON-aware files.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--collection",
        required=True,
        choices=("variants", "variants_idref") if version == 2 else ("variants",),
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--sample-bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--select-missing-csq", action="store_true")
    parser.add_argument("--hgnc-genes", type=Path)
    parser.add_argument("--prior-bundle", action="append", type=Path, default=[])
    args = parser.parse_args()
    if args.select_missing_csq != bool(args.hgnc_genes):
        parser.error("Use --select-missing-csq and --hgnc-genes together")
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    counts: Counter = Counter()
    seen: dict[str, set[str]] = {"variants": set(), "finding_comments": set()}
    alleles: set[tuple[str, str]] = set()
    current = None

    def write(name: str, row: Document) -> None:
        """Append a canonical Extended JSON document to the protected output directory."""
        with (args.output / f"{name}.jsonl").open("a") as stream:
            stream.write(json_util.dumps(row, json_options=json_util.CANONICAL_JSON_OPTIONS) + "\n")

    try:
        samples = sample_bundle(args.sample_bundle, version)["samples"]
        reviews = json_util.loads(args.review.read_text()).get("records", {}) if args.review else {}
        hgnc_rows = list(json_rows(args.hgnc_genes)) if args.hgnc_genes else None
        if hgnc_rows is not None and not any(
            (r.get("hgnc_id") or r.get("_id")) and r.get("hgnc_symbol") for r in hgnc_rows
        ):
            raise ValueError("HGNC export must contain HGNC identities and hgnc_symbol records")
        hgnc = build_hgnc_lookup_maps(hgnc_rows) if hgnc_rows is not None else None
        with TemporaryDirectory(dir=args.output, prefix="vep-staging-") as directory:
            staging = Path(directory)

            def vault(row: Document) -> None:
                """Merge one allele/release on disk, keeping memory bounded by one vault row."""
                path = staging / f"{row['_id']}.json"
                if path.exists():
                    row = merge_vault(json_util.loads(path.read_text()), row)
                path.write_text(json_util.dumps(row))

            for prior in args.prior_bundle:
                manifest = json.loads((prior / "manifest.json").read_text())
                if manifest.get("complete") is not True or manifest.get("kind") != "variants":
                    raise ValueError("Prior bundle must be a complete variant bundle")
                for name, digest in manifest["sha256"].items():
                    if Path(name).name != name or file_hash(prior / name) != digest:
                        raise ValueError("Prior bundle checksum is invalid")
                for name in ("variants", "finding_comments", "anno_vep"):
                    if f"{name}.jsonl" not in manifest["sha256"]:
                        continue
                    for row in json_rows(prior / f"{name}.jsonl"):
                        if name == "anno_vep":
                            vault(validate(name, row))
                        else:
                            seen[name].add(str(row["_id"]))
                            if name == "variants":
                                alleles.add((row["SAMPLE_ID"], row["simple_id_hash"]))
            for current in json_rows(args.input):
                counts["input"] += 1
                raw_owner = current.get("SAMPLE_ID")
                if raw_owner is None or not ObjectId.is_valid(str(raw_owner)):
                    counts["unlinked"] += 1
                    continue
                owner = str(ObjectId(str(raw_owner)))
                if owner not in samples:
                    counts["outside_selection"] += 1
                    continue
                records = convert(
                    current,
                    samples[owner],
                    review=reviews.get(str(current["_id"])),
                    hgnc=hgnc,
                )
                variant = records["variants"][0]
                identity = (owner, variant["simple_id_hash"])
                if identity in alleles:
                    raise ValueError(
                        "Duplicate sample/allele across sources; reconcile before import"
                    )
                alleles.add(identity)
                for name in ("variants", "finding_comments"):
                    for row in records[name]:
                        if str(row["_id"]) in seen[name]:
                            raise ValueError("Duplicate finding or comment ObjectId")
                        seen[name].add(str(row["_id"]))
                        write(name, row)
                vault(records["anno_vep"][0])
                write("source_records", current)
                counts["selected"] += 1
            if not counts["selected"]:
                raise ValueError(
                    "No selected variants; check the source collection and sample bundle"
                )
            for path in sorted(staging.glob("*.json")):
                write("anno_vep", json_util.loads(path.read_text()))
        manifest = {
            "complete": True,
            "kind": "variants",
            "source_version": version,
            "source_collection": args.collection,
            "counts": dict(counts),
            "source_sha256": file_hash(args.input),
            "sample_bundle_manifest_sha256": file_hash(args.sample_bundle / "manifest.json"),
            "source_vep_version": SOURCE_VEP_VERSION,
            "hgnc_sha256": file_hash(args.hgnc_genes) if args.hgnc_genes else None,
            "review_sha256": file_hash(args.review) if args.review else None,
            "prior_bundles": [file_hash(p / "manifest.json") for p in args.prior_bundle],
            "sha256": {p.name: file_hash(p) for p in args.output.glob("*.jsonl")},
        }
        (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"[ok] {counts['selected']} variants prepared; no database writes")
        return 0
    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as error:
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
