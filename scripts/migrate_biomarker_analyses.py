#!/usr/bin/env python3
"""Plan or apply independent biomarker analysis and file-key configuration."""

from __future__ import annotations

import argparse
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.config.constants import analysis_file_keys  # noqa: E402
from api.config.loaders.collections import load_collection_section  # noqa: E402
from api.contracts.schemas.dna import BiomarkersDoc  # noqa: E402
from api.domain.common.biomarkers import BIOMARKER_ANALYSES, biomarker_counts  # noqa: E402
from api.infra.mongo.transactions import run_transaction  # noqa: E402


def transform_configuration(document: dict[str, Any], analyses: list[str]) -> dict[str, Any]:
    """Expand legacy analysis/file selections in configuration trees.

    Args:
        document: ASP, ASPC, or unpublished assay-setup document.
        analyses: Clinically reviewed replacement selection for BIOMARKER.

    Returns:
        A copy with explicit analysis identifiers and independent file requirements.
        Existing individual selections retain their order and are deduplicated.
    """
    result = deepcopy(document)
    for key, value in result.items():
        if key in {
            "analysis_types",
            "report_sections",
            "expected_files",
            "required_files",
        } and isinstance(value, list):
            old = "biomarkers" if key.endswith("files") else "BIOMARKER"
            replacements = (
                [item.lower() for item in analyses] if key.endswith("files") else analyses
            )
            result[key] = list(
                dict.fromkeys(
                    item for entry in value for item in (replacements if entry == old else [entry])
                )
            )
        elif isinstance(value, dict):
            result[key] = transform_configuration(value, analyses)
        elif isinstance(value, list):
            result[key] = [
                transform_configuration(item, analyses) if isinstance(item, dict) else item
                for item in value
            ]
    return result


def requires_rule_review(value: Any) -> bool:
    """Identify obsolete measurement declarations, collections, and aggregate facts.

    Args:
        value: A stored rule document or nested rule expression.

    Returns:
        Whether a reviewed replacement release is required before migration.
    """
    if isinstance(value, dict):
        if {"BIOMARKER", "LOH"} & set(value.get("analysis_declarations", {})):
            return True
        if value.get("analysis") in {"BIOMARKER", "LOH"}:
            return True
        if value.get("collection") in {"biomarkers", "loh"}:
            return True
        return any(requires_rule_review(item) for item in value.values())
    if isinstance(value, list):
        return any(requires_rule_review(item) for item in value)
    return value == "aggregates.biomarker_count"


def migrate(db: Any, *, analyses: list[str], apply: bool = False) -> dict[str, int]:
    """Migrate configuration and sample file metadata in one transaction.

    Args:
        db: Explicit application database with configured collection names.
        analyses: Explicit replacement for the generic selection; no clinical inference.
        apply: False performs preflight only. True applies the complete reviewed plan.

    Returns:
        Counts of changed configuration and sample documents and blocking rule releases.

    Raises:
        ValueError: Selection is invalid, a rule or setup needs review, or a concurrent
            writer changes a planned document.

    Notes:
        Stop writers and take a backup before applying. Stored measurements, saved
        reports, reported findings, rule revisions, and published setup snapshots are
        not rewritten. Files may share their existing JSON path; each parser selects
        only its own measurement fields. Required generic files expand to every selected
        analysis, so operators must review requirements and producer output first.
    """
    if (
        not analyses
        or len(set(analyses)) != len(analyses)
        or set(analyses) - set(BIOMARKER_ANALYSES)
    ):
        raise ValueError("Select distinct HRD, MSI, and/or TMB analyses explicitly")
    mapping = load_collection_section("primary")
    rules = db[mapping["clinical_rule_sets_collection"]]
    blockers = sum(
        1
        for rule in rules.find({"active": True, "status": "published"})
        if requires_rule_review(rule)
    )
    counts = {"configurations": 0, "samples": 0, "rules_requiring_review": blockers}
    changes = []
    for key in ("asp_collection", "aspc_collection", "assay_setups_collection"):
        collection = db[mapping[key]]
        for original in collection.find({}):
            if key == "assay_setups_collection" and original.get("status") == "published":
                continue
            updated = transform_configuration(original, analyses)
            if updated == original:
                continue
            if key == "assay_setups_collection" and original.get("status") != "draft":
                raise ValueError("Return affected assay setups to draft before migration")
            changes.append((collection, original, updated))
            counts["configurations"] += 1
    panels = {
        document["asp_id"]: transform_configuration(document, analyses)
        for document in db[mapping["asp_collection"]].find({"is_active": {"$ne": False}})
    }
    for document in db[mapping["aspc_collection"]].find({}):
        updated = transform_configuration(document, analyses)
        enabled = set(updated.get("analysis_types") or []) & set(BIOMARKER_ANALYSES)
        if not enabled:
            continue
        panel = panels.get(updated.get("asp_id"))
        if panel is None:
            raise ValueError(
                "An affected ASPC has no active ASP; reconcile the assay before migration"
            )
        if "expected_files" in panel:
            expected = set(panel["expected_files"])
            for analysis in enabled:
                if not set(analysis_file_keys("dna", analysis)) <= expected:
                    raise ValueError(
                        f"{analysis} remains enabled without its expected file; review the explicit migration selection"
                    )
    samples = db[mapping["samples_collection"]]
    measurements = db[mapping["biomarkers_collection"]]
    for original in samples.find({}):
        updated = deepcopy(original)
        files = updated.get("files") or {}
        legacy = files.pop("biomarkers", None)
        if legacy is not None:
            for analysis in analyses:
                files.setdefault(analysis.lower(), deepcopy(legacy))
            updated["files"] = files
        if "biomarkers" in updated.get("missing_expected_files", []):
            updated["missing_expected_files"] = list(
                dict.fromkeys(
                    item
                    for entry in updated["missing_expected_files"]
                    for item in (
                        [analysis.lower() for analysis in analyses]
                        if entry == "biomarkers"
                        else [entry]
                    )
                )
            )
        documents = list(measurements.find({"SAMPLE_ID": str(original["_id"])}))
        for document in documents:
            BiomarkersDoc.model_validate(document)
        if documents:
            updated.setdefault("data_counts", {}).update(biomarker_counts(documents))
        if updated != original:
            changes.append((samples, original, updated))
            counts["samples"] += 1
    if apply:
        if blockers:
            raise ValueError(
                "Publish reviewed individual-analysis rules before applying; existing rule releases are not rewritten"
            )

        def write(session: Any) -> None:
            """Apply the plan atomically, rejecting concurrent changes."""
            for collection, original, updated in changes:
                if collection.replace_one(original, updated, session=session).matched_count != 1:
                    raise ValueError("A planned document changed; rerun preflight")

        run_transaction(db.client, write)
    return counts


def main() -> int:
    """Print a read-only plan unless --apply enables the reviewed transaction."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mongo-uri", default=os.environ.get("COYOTE3_MONGO_URI"))
    parser.add_argument("--db", default=os.environ.get("COYOTE3_DB"))
    parser.add_argument("--analyses", nargs="+", required=True, choices=BIOMARKER_ANALYSES)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.mongo_uri or not args.db:
        parser.error("COYOTE3_MONGO_URI and COYOTE3_DB or explicit overrides are required")
    with MongoClient(args.mongo_uri, serverSelectionTimeoutMS=7000) as client:
        counts = migrate(client[args.db], analyses=args.analyses, apply=args.apply)
    print(f"{'Migrated' if args.apply else 'Would migrate'}: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
