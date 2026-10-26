"""Enrich migrated case/control metadata from read-only Bjorn and CDM evidence."""

from __future__ import annotations

import json
import re
import shlex
import subprocess
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from bson import json_util

from migrations_scripts.common import validate

Document = dict[str, Any]


def field_values(document: Any, path: str) -> list[Any]:
    """Read an explicitly configured dotted field through nested documents and arrays.

    Args:
        document: Original reference record; its fields are not modified.
        path: Verified source field path, not an assumed CDM schema.

    Returns:
        Flattened leaf values; missing/null fields yield no values.
    """
    if isinstance(document, list):
        return [value for item in document for value in field_values(item, path)]
    if not path:
        return [] if document is None else [document]
    head, _, tail = path.partition(".")
    if not isinstance(document, dict) or head not in document:
        return []
    return field_values(document[head], tail)


class ReferenceReader:
    """Read reference records with legacy mongoexport over SSH or from a local export."""

    def __init__(self, config: Document, workspace: Path) -> None:
        """Validate reference connection and explicitly mapped matching fields.

        Args:
            config: database, collection, sample_id_field and assay_field; either input
                for an offline export or ssh_host for a server with legacy mongoexport.
            workspace: Protected migration output used for temporary source extracts.

        Raises:
            ValueError: Required mapping/connection fields are missing or unsafe.
        """
        self.config = config
        self.workspace = workspace
        for key in ("database", "collection", "sample_id_field", "assay_field"):
            if not isinstance(config.get(key), str) or not config[key].strip():
                raise ValueError("Reference database, collection and identity fields are required")
        for key in ("sample_id_field", "assay_field"):
            if any(not part or part.startswith("$") for part in config[key].split(".")):
                raise ValueError("Reference identity fields must be plain dotted paths")
        if bool(config.get("input")) == bool(config.get("ssh_host")):
            raise ValueError("Reference needs exactly one input export or SSH host")
        if config.get("ssh_host", "").startswith("-"):
            raise ValueError("Invalid reference SSH destination")

    def records(self, sample_id: str, assays: list[str]) -> list[Document]:
        """Read one exact sample identity within the operator-confirmed source assay scope.

        Args:
            sample_id: Original specimen identifier; never lowercased or inferred from a path.
            assays: Explicit reference assay identifiers approved for the migrated ASP.

        Returns:
            Original matching reference documents with BSON types preserved.

        Raises:
            ValueError: A reference export is malformed or returned a different identity.
            CalledProcessError: An SSH or mongoexport read fails; never treated as no records.
        """
        config = self.config
        query = {
            "$and": [
                {config["sample_id_field"]: sample_id},
                {
                    "$or": [
                        {
                            config["assay_field"]: {
                                "$regex": f"^{re.escape(assay)}$",
                                "$options": "i",
                            }
                        }
                        for assay in assays
                    ]
                },
            ]
        }
        with TemporaryDirectory(dir=self.workspace, prefix="reference-read-") as directory:
            if config.get("input"):
                path = Path(config["input"])
            else:
                path = Path(directory) / "records.jsonl"
                command = [
                    config.get("mongoexport", "mongoexport"),
                    "--host",
                    config.get("host", "127.0.0.1"),
                    "--port",
                    str(config.get("port", 27017)),
                    "--db",
                    config["database"],
                    "--collection",
                    config["collection"],
                    "--query",
                    json.dumps(query),
                ]
                with (
                    path.open("w") as output,
                    (self.workspace / "reference-read.stderr").open("w") as errors,
                ):
                    subprocess.run(
                        [
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
                            config["ssh_host"],
                            shlex.join(command),
                        ],
                        stdout=output,
                        stderr=errors,
                        check=True,
                    )
            selected = []
            with path.open() as stream:
                for line in stream:
                    if not line.strip():
                        continue
                    row = json_util.loads(line)
                    if not isinstance(row, dict):
                        raise ValueError("Reference exports must contain documents")
                    matches = sample_id in field_values(row, config["sample_id_field"]) and any(
                        isinstance(value, str)
                        and value.lower() in {assay.lower() for assay in assays}
                        for value in field_values(row, config["assay_field"])
                    )
                    if matches:
                        selected.append(row)
                    elif not config.get("input"):
                        raise ValueError("Reference query returned an unexpected sample or assay")
            return selected


def select_runs(bjorn: list[Document], cdm: list[Document], cdm_run_field: str) -> Document:
    """Choose nonfailed Bjorn runs, retaining multiple runs only when CDM confirms them.

    Args:
        bjorn: Exact sample/assay matches from Bjorn samples with replicates arrays.
        cdm: Exact sample/assay matches from the configured CDM collection.
        cdm_run_field: Verified path containing CDM's recorded run names, scalar or array.

    Returns:
        Case/control metadata plus a receipt describing selected/failed runs and the rule.
        Multiple confirmed runs use a list; otherwise the latest eligible Bjorn run is used.

    Raises:
        ValueError: Run identity/date/status or retained measurement metadata is ambiguous.
    """
    candidates: dict[str, Document] = {}
    failed = []
    for sample in bjorn:
        replicates = sample.get("replicates")
        if not isinstance(replicates, list):
            raise ValueError("Bjorn sample replicates must be an array")
        for replicate in replicates:
            if not isinstance(replicate, dict) or not isinstance(replicate.get("paths"), dict):
                raise ValueError("Bjorn replicates require a paths document")
            run = replicate.get("paths", {}).get("sequencing_run")
            status = str(replicate.get("status") or "normal").strip().lower()
            if status == "failed":
                if isinstance(run, str) and run.strip():
                    failed.append(run)
                else:
                    raise ValueError("Failed Bjorn runs require a name for exclusion")
                continue
            if status not in {"normal", "topup"}:
                raise ValueError("Unknown Bjorn run status requires review")
            date = replicate.get("sequencing_date")
            if not isinstance(run, str) or not run.strip() or not isinstance(date, datetime):
                raise ValueError("Nonfailed Bjorn runs require a name and recorded sequencing_date")
            entry = deepcopy(replicate)
            entry["sequencing_date"] = (
                date.replace(tzinfo=UTC) if date.tzinfo is None else date.astimezone(UTC)
            )
            if run in candidates and candidates[run] != entry:
                raise ValueError("Duplicate Bjorn run has conflicting metadata")
            candidates[run] = entry
    for run in failed:
        candidates.pop(run, None)
    if not candidates:
        raise ValueError("No nonfailed Bjorn sequencing runs match this sample and assay")
    cdm_names = set()
    for document in cdm:
        for value in field_values(document, cdm_run_field):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("CDM run names must be nonblank text")
            cdm_names.add(value)
    ordered = sorted(candidates, key=lambda name: (candidates[name]["sequencing_date"], name))
    confirmed = [name for name in ordered if name in cdm_names]
    if len(confirmed) >= 2:
        selected = confirmed
        rule = "multiple_runs_confirmed_by_cdm"
    else:
        latest_date = candidates[ordered[-1]]["sequencing_date"]
        if sum(candidates[name]["sequencing_date"] == latest_date for name in ordered) > 1:
            raise ValueError("Latest Bjorn run is ambiguous because sequencing dates tie")
        selected = [ordered[-1]]
        rule = "latest_nonfailed_bjorn_run_cdm_confirms_fewer_than_two"
    latest = candidates[selected[-1]]
    if (
        sum(candidates[name]["sequencing_date"] == latest["sequencing_date"] for name in selected)
        > 1
    ):
        raise ValueError("Latest selected Bjorn metadata is ambiguous because sequencing dates tie")
    metadata: Document = {"sequencing_run": selected if len(selected) > 1 else selected[0]}
    for source, target in (
        ("clarity_sample_id", "clarity_id"),
        ("clarity_pool_id", "clarity_pool_id"),
    ):
        if latest.get(source) is not None:
            metadata[target] = latest[source]
    reads = [candidates[name].get("n_reads") for name in selected]
    if any(
        value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0)
        for value in reads
    ):
        raise ValueError("Bjorn n_reads must be nonnegative integers")
    if all(value is not None for value in reads):
        metadata["reads"] = sum(reads)
    else:
        metadata["reads"] = None
    for key in ("ffpe", "purity"):
        if latest.get(key) is not None:
            value = latest[key]
            if key == "ffpe" and isinstance(value, str):
                if value.strip().lower() not in {"true", "false", "yes", "no", "1", "0"}:
                    raise ValueError("Unrecognized Bjorn FFPE value")
                value = value.strip().lower() in {"true", "yes", "1"}
            metadata[key] = value
    return {
        "metadata": metadata,
        "selected_runs": selected,
        "failed_runs": sorted(set(failed)),
        "cdm_runs": sorted(cdm_names),
        "rule": rule,
    }


class CaseControlEnricher:
    """Resolve reference evidence for both specimen roles without source database writes."""

    def __init__(self, config_path: Path, assay: str, workspace: Path) -> None:
        """Load explicit source mappings, requiring CDM fields instead of guessing them.

        Args:
            config_path: Operator-reviewed JSON with bjorn/cdm readers and per-ASP assays.
            assay: Destination assay selected by the version-specific sample converter.
            workspace: Protected output directory for reference extracts and diagnostics.

        Raises:
            ValueError: Reference mapping or an assay selection is missing.
        """
        config = json.loads(config_path.read_text())
        self.scope = config.get("assays", {}).get(assay)
        if not isinstance(self.scope, dict) or any(
            not isinstance(self.scope.get(key), list)
            or not self.scope[key]
            or any(not isinstance(value, str) or not value.strip() for value in self.scope[key])
            for key in ("bjorn", "cdm")
        ):
            raise ValueError(
                "Configure explicit Bjorn and CDM assay identifiers for the selected ASP"
            )
        bjorn = config.get("bjorn", {})
        if any(
            bjorn.get(key) != value
            for key, value in {
                "database": "bjorn",
                "collection": "samples",
                "sample_id_field": "id",
                "assay_field": "assay",
            }.items()
        ):
            raise ValueError("Bjorn must use the inspected bjorn.samples id/assay structure")
        cdm = config.get("cdm", {})
        self.run_field = cdm.get("run_field")
        if not isinstance(self.run_field, str) or any(
            not part or part.startswith("$") for part in self.run_field.split(".")
        ):
            raise ValueError("Configure CDM's verified run-name field")
        self.bjorn = ReferenceReader(bjorn, workspace)
        self.cdm = ReferenceReader(cdm, workspace)

    def enrich(self, sample: Document) -> tuple[Document, Document]:
        """Enrich every recorded case/control independently and retain raw reference evidence.

        Args:
            sample: Converted sample retaining its original BSON identity and specimen IDs.

        Returns:
            Validated enriched sample and a private evidence record, keyed by sample ObjectId.
            Existing BAM/index paths and unrelated history remain unchanged.

        Raises:
            ValueError: Specimen identities conflict or evidence cannot resolve an eligible run.
        """
        enriched = deepcopy(sample)
        evidence: Document = {"_id": sample["_id"], "asp_id": sample["asp_id"]}
        for role in ("case", "control"):
            identifier = sample.get(f"{role}_id")
            if identifier is None and role == "control":
                continue
            if not isinstance(identifier, str) or not identifier:
                raise ValueError("Reference enrichment requires each recorded specimen identifier")
            block = enriched.get(role) or {}
            if block.get("id") not in (None, identifier):
                raise ValueError("Nested case/control identity conflicts with specimen identifier")
            bjorn = self.bjorn.records(identifier, self.scope["bjorn"])
            cdm = self.cdm.records(identifier, self.scope["cdm"])
            decision = select_runs(bjorn, cdm, self.run_field)
            block.update(decision["metadata"])
            block["id"] = identifier
            enriched[role] = block
            evidence[role] = {
                "specimen_id": identifier,
                "bjorn_documents": bjorn,
                "cdm_documents": cdm,
                **decision,
            }
        return validate("samples", enriched), evidence
