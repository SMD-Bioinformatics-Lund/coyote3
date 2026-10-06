"""Offline command entry points shared by the v2 and v3 migration packages."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path

from pydantic import ValidationError

from api.contracts.schemas.registry import COLLECTION_MODEL_ADAPTERS
from scripts.migration_common.conversion import independent_plan, sample_plan, supplement
from scripts.migration_common.offline import (
    SOURCE_COLLECTIONS,
    RecordConversionError,
    SourceIndex,
    digest,
    prepare_source,
    private_json,
    read_json,
    write_bundle,
)
from scripts.migration_common.run_report import write_report
from scripts.migration_common.schema_inventory import verify_review
from scripts.migration_common.target_catalog import (
    bind_sample_review,
    validate_plan_scope,
    validate_snapshot,
)

BACKFILL_FIELDS = {
    "case.sequencing_run": str,
    "control.sequencing_run": str,
    "case.reads": int,
    "control.reads": int,
    "case_id": str,
    "control_id": str,
    "sample_no": int,
    "pipeline": str,
    "pipeline_version": str,
    "database_versions.vep": str,
    "genome_build": int,
}


def build_backfill_review(read_sample: Callable[[str], dict], tsv: Path, review: dict) -> dict:
    """Add missing sample metadata from a reviewed UTF-8 tab-separated text file.

    Args:
        read_sample: Read one original sample by its string identity.
        tsv: Columns sample_id, field, value, evidence. Blank values are rejected.
        review: Existing reconciliation document; returned as an updated copy.

    Returns:
        Reconciliation data consumed by migrate_sample.py. Existing values and
        prior supplements cannot be overwritten. No database or source index is changed.
    """
    result = deepcopy(review)
    seen = set()
    with tsv.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if reader.fieldnames != ["sample_id", "field", "value", "evidence"]:
            raise ValueError("TSV header must be sample_id, field, value, evidence in that order")
        for row in reader:
            if None in row or any(not value or not value.strip() for value in row.values()):
                raise ValueError("TSV rows require all four nonblank columns")
            identity, field = row["sample_id"], row["field"]
            if field not in BACKFILL_FIELDS or (identity, field) in seen:
                raise ValueError("Unsupported or duplicate backfill field")
            seen.add((identity, field))
            try:
                value = BACKFILL_FIELDS[field](row["value"])
            except ValueError:
                raise ValueError(
                    "Backfill value does not match the field's declared type"
                ) from None
            if isinstance(value, int) and value < 0:
                raise ValueError("Counts and numeric metadata cannot be negative")
            original = read_sample(identity)
            if field.startswith("control.") and not original.get("control_id"):
                raise ValueError("Control metadata requires a recorded control identity")
            sample_review = (
                result.setdefault("samples", {}).setdefault(identity, {}).setdefault("sample", {})
            )
            entry = sample_review.setdefault(
                "supplement",
                {
                    "source_sha256": digest(original),
                    "reason": "Reviewed metadata TSV",
                    "fields": {},
                },
            )
            if field in entry["fields"] and entry["fields"][field] != value:
                raise ValueError("Backfill conflicts with an existing supplement")
            entry["fields"][field] = value
            entry.setdefault("evidence", {})[field] = row["evidence"]
            supplement(original, entry)
    return result


def backfill_review(source: SourceIndex, tsv: Path, review: dict) -> dict:
    """Build missing-field supplements from a local read-only source index and TSV."""
    return build_backfill_review(lambda identity: source.get("samples", identity), tsv, review)


def backfill_bundle(bundle: Path, tsv: Path, output: Path, version: int) -> dict:
    """Prepare missing run/read metadata updates for an already imported sample bundle.

    Args:
        bundle: Original applied bundle, retained for optimistic conflict checks and recovery.
        tsv: Reviewed text file; only case/control run names and read counts may change later.
        output: New private patch bundle directory.
        version: Expected major source version.

    Returns:
        Counts in the patch bundle. Target changes require a separate explicit apply.
    """
    from scripts.migration_common.apply_bundle import load_bundle

    manifest = read_json(bundle / "manifest.json")
    if manifest.get("provenance", {}).get("source_version") != version:
        raise ValueError("Bundle belongs to another source version")
    originals = {str(row["_id"]): row for row in load_bundle(bundle).get("samples", [])}

    def read_sample(identity: str) -> dict:
        """Reject text-file identifiers absent from the original applied bundle."""
        if identity not in originals:
            raise ValueError("Backfill references a sample absent from the original bundle")
        return originals[identity]

    review = build_backfill_review(read_sample, tsv, {})
    updates, expected = [], {}
    for identity, item in review.get("samples", {}).items():
        additions = item["sample"]["supplement"]
        if set(additions["fields"]) - {
            "case.reads",
            "case.sequencing_run",
            "control.reads",
            "control.sequencing_run",
        }:
            raise ValueError("After import, this backfill supports only run names and read counts")
        converted = supplement(originals[identity], additions)
        COLLECTION_MODEL_ADAPTERS["samples"].validate_python(converted)
        updates.append(converted)
        expected[identity] = digest(originals[identity])
    return write_bundle(
        output,
        {"samples": updates},
        provenance={
            "operation": "metadata_backfill",
            "source_version": version,
            "target_sha256": manifest.get("provenance", {}).get("target_sha256"),
            "expected_samples": expected,
            "review": review,
        },
    )


def run(version: int, operation: str) -> int:
    """Execute one version-specific offline operation and print only aggregate results."""
    parser = argparse.ArgumentParser(description=f"Offline Coyote v{version} {operation}")
    conversion = operation in {
        "sample",
        "annotation",
        "blacklist",
        "d4_coverage_blacklist",
    }
    if conversion:
        parser.add_argument("--schema-audit", type=Path, required=True)
        parser.add_argument("--target-catalog", type=Path, required=True)
    reporting = conversion or operation == "backfill"
    if reporting:
        parser.add_argument(
            "--report", type=Path, help="New private JSON run report; Markdown is also written"
        )
    parser.add_argument(
        "--issues", type=Path, help="New private file for blocked record coordinates"
    )
    if operation == "backfill":
        origin = parser.add_mutually_exclusive_group(required=True)
        origin.add_argument("--index", type=Path)
        origin.add_argument("--bundle", type=Path)
    else:
        parser.add_argument("--index", type=Path, required=True)
    if operation == "prepare":
        parser.add_argument("--export-dir", type=Path, required=True)
    else:
        parser.add_argument("--output", type=Path, required=True)
        parser.add_argument("--review", type=Path, required=conversion)
    if operation == "sample":
        parser.add_argument("--sample-id", required=True)
    if operation == "inspect":
        parser.add_argument("--collection", choices=SOURCE_COLLECTIONS[version], required=True)
        parser.add_argument("--record-id", required=True)
    if operation == "backfill":
        parser.add_argument("--tsv", type=Path, required=True)
    args = parser.parse_args()
    source = None
    report_path = None
    plan = None
    failure = None
    provenance = {"source_version": version, "operation": operation}
    try:
        if reporting:
            candidate = args.report or args.output.with_name(args.output.name + ".migration.json")
            if candidate.exists() or candidate.with_suffix(".md").exists():
                raise FileExistsError("Run reports must use new paths")
            report_path = candidate
        if operation == "prepare":
            print(json.dumps(prepare_source(args.export_dir, args.index, version)))
            return 0
        if operation == "backfill" and args.bundle:
            if args.review:
                raise ValueError("Bundle backfill does not accept a source review file")
            print(json.dumps(backfill_bundle(args.bundle, args.tsv, args.output, version)))
            return 0
        source = SourceIndex(args.index, version)
        provenance["source_sha256"] = source.fingerprint()
        review = read_json(args.review) if args.review else {}
        if operation == "inspect":
            original = source.get(args.collection, args.record_id)
            evidence = {"source_sha256": digest(original), "document": original}
            if args.collection == "samples":
                evidence["filters_source_sha256"] = digest(
                    {
                        key: value
                        for key, value in original.items()
                        if key == "filters"
                        or key.startswith("filter_")
                        or key.startswith("checked_")
                    }
                )
                if version == 3:
                    candidates = [
                        {"collection": name, "document": row}
                        for name in ("panel_cov", "group_coverage")
                        for row in source.rows(name, args.record_id)
                        if name == "panel_cov" or "genes" in row
                    ]
                    evidence["d4_coverage_source_sha256"] = digest(candidates)
                    evidence["d4_coverage_candidates"] = [
                        {"collection": item["collection"], "record_id": item["document"]["_id"]}
                        for item in candidates
                    ]
                from api.config.constants import ALL_SAMPLE_FILE_KEYS

                evidence["files_source_sha256"] = digest(
                    {key: original[key] for key in ALL_SAMPLE_FILE_KEYS if key in original}
                )
            private_json(args.output, evidence)
            print("Private source evidence written; no database was accessed.")
            return 0
        if operation == "backfill":
            private_json(args.output, backfill_review(source, args.tsv, review))
            print("Reviewed metadata file written; no database was accessed.")
            return 0
        audit_digest = verify_review(source, args.schema_audit, review)
        catalog = read_json(args.target_catalog)
        validate_snapshot(catalog)
        provenance.update(source_sha256=source.fingerprint(), target_sha256=catalog["sha256"])
        if operation == "sample":
            sample_review = bind_sample_review(
                catalog,
                source.get("samples", args.sample_id),
                review.get("samples", {}).get(args.sample_id, {}),
            )
            plan = sample_plan(source, args.sample_id, sample_review)
        else:
            plan = independent_plan(source, operation, review.get(operation, {}))
        validate_plan_scope(catalog, plan)
        provenance.update(
            {
                "source_version": version,
                "source_sha256": source.fingerprint(),
                "review_sha256": digest(review),
                "operation": operation,
                "schema_audit_sha256": audit_digest,
            }
        )
        if operation == "sample":
            provenance["sample_id"] = args.sample_id
            provenance["coverage_reconciliation"] = (
                review.get("samples", {}).get(args.sample_id, {}).get("d4_coverage")
            )
            provenance["configuration_binding"] = sample_review.get("sample", {}).get(
                "metadata", {}
            )
        print(json.dumps(write_bundle(args.output, plan, provenance=provenance)))
        return 0
    except Exception as error:
        failure = error
        # Validation exception messages can contain clinical values. Never log input values.
        print(f"Offline migration stopped: {type(error).__name__}", file=sys.stderr)
        if isinstance(error, RecordConversionError) and args.issues:
            private_json(args.issues, error.issue)
        if isinstance(error, ValidationError):
            print(
                json.dumps(
                    [{"field": item["loc"], "error": item["type"]} for item in error.errors()]
                ),
                file=sys.stderr,
            )
        elif isinstance(error, ValueError):
            print(str(error), file=sys.stderr)
        return 1
    finally:
        if source is not None:
            source.close()
        if report_path is not None:
            write_report(report_path, provenance, plan, failure)
