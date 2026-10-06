"""Write private, exclusive per-run evidence without exposing patient values to the terminal."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from scripts.migration_common.offline import RecordConversionError, private_json


def gaps(value: object, path: str = "") -> list[str]:
    """List stored null or blank fields without inventing replacement values."""
    if isinstance(value, dict):
        return [
            field
            for key, item in value.items()
            for field in gaps(item, f"{path}.{key}" if path else key)
        ]
    if isinstance(value, list):
        return sorted({field for item in value for field in gaps(item, path + "[]")})
    return [path] if value is None or value == "" else []


def write_report(path: Path, details: dict, plan: dict | None, error: Exception | None) -> None:
    """Write a JSON report and a Markdown companion, including failed conversions.

    Args:
        path: New private JSON report path, reserved before conversion; a sibling .md
            report is created exclusively. Existing reports must never be overwritten.
        details: Operation, version, source/target digests, and reviewed decisions.
        plan: Converted documents on success, otherwise None.
        error: Caught conversion failure, otherwise None.

    Notes:
        Reports contain original record IDs and are private operational artifacts.
        They are not repository documentation and must not be committed.
    """
    report = {
        **details,
        "finished_on": datetime.now(timezone.utc).isoformat(),
        "status": "blocked" if error else "complete",
        "counts": {name: len(rows) for name, rows in (plan or {}).items()},
        "unrecorded_values": [
            {"collection": name, "record_id": str(row.get("_id")), "fields": fields}
            for name, rows in (plan or {}).items()
            for row in rows
            if (fields := gaps(row))
        ],
    }
    missing_history = []
    for sample in (plan or {}).get("samples", []):
        fields = ["pipeline_version", "ingested_by", "case.sequencing_run", "case.reads"]
        if sample.get("control_id"):
            fields.extend(["control.sequencing_run", "control.reads"])
        absent = []
        for field in fields:
            value = sample
            for part in field.split("."):
                value = value.get(part) if isinstance(value, dict) else None
            if value is None or value == "":
                absent.append(field)
        if absent:
            missing_history.append({"record_id": str(sample["_id"]), "fields": absent})
    report["unrecorded_sample_history"] = missing_history
    if error:
        report["error_type"] = type(error).__name__
        if isinstance(error, RecordConversionError):
            report["issue"] = error.issue
        elif isinstance(error, ValidationError):
            report["fields"] = [
                {"field": list(item["loc"]), "error": item["type"]} for item in error.errors()
            ]
        elif isinstance(error, ValueError):
            report["reason"] = str(error)
    private_json(path, report)
    with path.with_suffix(".md").open("x", encoding="utf-8") as stream:
        os.chmod(stream.name, 0o600)
        stream.write(f"# Migration run: {details['operation']}\n\n")
        stream.write(
            f"Status: **{report['status']}**. Source version: {details['source_version']}.\n\n"
        )
        stream.write(
            "The adjacent JSON report contains snapshot fingerprints, counts, "
            "review decisions, and unrecorded or blocked fields.\n\n"
        )
        if details["operation"] == "apply" and not error:
            stream.write("The destination transaction and post-write verification completed.\n")
        else:
            stream.write(
                "No source database writes were performed. A converted bundle has not "
                "been applied until the separate destination apply step succeeds.\n"
            )
