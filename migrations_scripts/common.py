"""Read legacy samples and prepare BSON-preserving files without database writes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from collections import Counter, defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from random import SystemRandom
from typing import Any, Callable

from bson import ObjectId, json_util
from pydantic import ValidationError
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from coyote3.contracts.schemas.registry import COLLECTION_MODEL_ADAPTERS

Document = dict[str, Any]

V2_ASSAY_RENAMES = {
    "myeloid": "myeloid_gmsv1",
    "solid": "solid_gmsv3",
    "hematology": "hema_gmsv1",
}


def v2_assay_identity(document: Document) -> str | None:
    """Resolve the physical ASP from v2 groups or the operator-mapped older assay.

    Args:
        document: Unmodified source sample. Newer groups contain one physical ASP;
            older group/assay records use the approved three-assay mapping.

    Returns:
        Lowercase physical ASP identifier, or None for missing or conflicting scope.
    """
    groups = document.get("groups")
    if isinstance(groups, str):
        groups = [groups]
    if groups is not None:
        if not isinstance(groups, list) or len(groups) > 1:
            return None
        if groups:
            value = str(groups[0]).lower()
            if value not in V2_ASSAY_RENAMES:
                return value
            if value != str(document.get("assay", "")).lower():
                return None
    return V2_ASSAY_RENAMES.get(str(document.get("assay", "")).lower())


SUBPANEL_RENAMES = {
    "bc": "breast",
    "bp": "breast-pilot",
    "crc": "crc",
    "lp": "lung",
    "none": "base",
    "": "base",
    "solid": "base",
    "hem": "hem",
    "hem-snabb": "hem-snabb",
    "kll": "kll",
    "mpn": "mpn",
    "riktad": "riktad",
    "allosct": "allo-sct",
    "lungthyroid": "lung-thyroid",
}


def normalize_scope(document: Document, *, unspecified_diagnosis: str = "base") -> None:
    """Canonicalize configuration identifiers using the approved subpanel renames.

    Args:
        document: Mutable copy of a sample, report scope or reviewed metadata.
        unspecified_diagnosis: Destination for blank or textual None subpanels;
            base normally, or legacy for the separately selected unsplit tumwgs cohort.

    Notes:
        Only explicit configuration keys are normalized. ObjectIds, usernames,
        case/control identifiers, labels and embedded historical content remain intact.
    """
    for key in (
        "asp_id",
        "asp_group",
        "diagnosis_id",
        "assay",
        "assay_group",
        "subpanel",
        "subpanel_id",
        "aspc_id",
        "isgl_id",
        "profile_id",
    ):
        if isinstance(document.get(key), str):
            document[key] = document[key].lower()
    for key in ("diagnosis_id", "subpanel", "subpanel_id"):
        value = document.get(key)
        if isinstance(value, str):
            document[key] = (
                unspecified_diagnosis
                if value in {"", "none"}
                else SUBPANEL_RENAMES.get(value, value)
            )
    filters = document.get("filters")
    if isinstance(filters, dict):
        for profile in filters.values():
            if not isinstance(profile, dict):
                continue
            for analysis in profile.values():
                if not isinstance(analysis, dict):
                    continue
                for key in ("snvlists", "cnvlists", "fusionlists"):
                    if isinstance(analysis.get(key), list):
                        analysis[key] = [
                            value.lower() if isinstance(value, str) else value
                            for value in analysis[key]
                        ]


def fingerprint(value: Any) -> str:
    """Hash canonical Extended JSON, retaining BSON types and array ordering.

    Args:
        value: BSON-serializable source document or destination content.

    Returns:
        SHA-256 digest for matching a review to its exact source record.
    """
    encoded = json_util.dumps(value, sort_keys=True, json_options=json_util.CANONICAL_JSON_OPTIONS)
    return hashlib.sha256(encoded.encode()).hexdigest()


def validate(collection: str, document: Document) -> Document:
    """Validate a destination record while requiring an explicit BSON identity.

    Args:
        collection: Current collection contract name.
        document: Converted record including its retained or deterministic identity.

    Returns:
        Validated MongoDB document with its BSON identity preserved.

    Raises:
        ValueError: The identity is absent or not an ObjectId.
        ValidationError: The record fails the current collection contract.
    """
    if not isinstance(document.get("_id"), ObjectId):
        raise ValueError(f"{collection} requires a BSON ObjectId")
    adapter = COLLECTION_MODEL_ADAPTERS[collection]
    return adapter.validate_python(document).model_dump(by_alias=True, exclude_unset=True)


def rename(document: Document, old: str, new: str) -> None:
    """Move a recorded field without accepting conflicting source values.

    Args:
        document: Mutable source copy.
        old: Legacy field to remove when present.
        new: Canonical destination field.

    Raises:
        ValueError: Both populated fields disagree.
    """
    if old not in document:
        return
    value = document.pop(old)
    if new in document and document[new] is not None and value is not None:
        if document[new] != value:
            raise ValueError(f"Conflicting fields: {old} / {new}")
    elif value is not None:
        document[new] = value


def derived_id(sample_id: ObjectId, collection: str, slot: str) -> ObjectId:
    """Assign a repeatable identity to an embedded record lacking its own ID.

    Args:
        sample_id: Original parent identity.
        collection: Destination collection, preventing cross-kind collisions.
        slot: Stable array index or embedded field name within the original source.

    Returns:
        Deterministic ObjectId; existing source ObjectIds must take precedence.
    """
    return ObjectId(fingerprint([str(sample_id), collection, slot])[:24])


def extract_history(document: Document) -> dict[str, list[Document]]:
    """Externalize comments, reports and embedded RNA results before sample validation.

    Args:
        document: Normalized mutable sample copy with original embedded history.

    Returns:
        Validated derived collections; the parent receives latest-report pointers.

    Raises:
        ValueError: History shape, ownership, IDs or report counters conflict.
        ValidationError: A derived record fails its current collection contract.
    """
    output: dict[str, list[Document]] = defaultdict(list)
    owner = document["_id"]
    for field, collection in (("comments", "sample_comments"), ("reports", "reports")):
        entries = document.pop(field, [])
        if not isinstance(entries, list):
            raise ValueError(f"{field} must be an array")
        for index, original in enumerate(entries):
            if not isinstance(original, dict):
                raise ValueError(f"{field} entries must be objects")
            record = deepcopy(original)
            if record.get("sample_oid", owner) != owner:
                raise ValueError("Embedded history has conflicting sample ownership")
            record.setdefault("_id", derived_id(owner, collection, str(index)))
            record.update(sample_oid=owner, sample_name=document["name"])
            if collection == "reports":
                normalize_scope(
                    record,
                    unspecified_diagnosis="legacy"
                    if document.get("asp_id") == "tumwgs"
                    else "base",
                )
                record.setdefault("report_id", str(record["_id"]))
                if record.get("filepath"):
                    record.setdefault("report_name", Path(record["filepath"]).name)
                # Report-time snapshots and recorded scope always take precedence.
                for key in ("asp_id", "diagnosis_id", "environment"):
                    record.setdefault(key, document.get(key))
            output[collection].append(validate(collection, record))
    reports = output["reports"]
    numbers = [r["report_num"] for r in reports]
    if len(numbers) != len(set(numbers)):
        raise ValueError("Duplicate report numbers")
    maximum = max(numbers, default=0)
    counter = document.pop("report_num", maximum)
    if counter != maximum:
        raise ValueError("Report counter disagrees with embedded report history")
    if reports:
        latest = max(reports, key=lambda row: row["report_num"])
        if document.get("latest_report_id", latest["_id"]) != latest["_id"]:
            raise ValueError("Latest report pointer disagrees with report history")
        if document.get("latest_report_on") not in (None, latest.get("time_created")):
            raise ValueError("Latest report timestamp disagrees with report history")
        document.update(
            reported=True,
            latest_report_id=latest["_id"],
            latest_report_on=latest.get("time_created"),
        )
    elif document.get("reported") or document.get("latest_report_id"):
        raise ValueError("Reported sample has no embedded report history")
    for field, collection in (
        ("expr", "rna_expression"),
        ("classification", "rna_classification"),
        ("QC", "rna_qc"),
    ):
        if field == "QC" and document.get("asp_category") != "rna":
            # Observed v2 DNA QC has a different schema; retain it on the sample.
            continue
        payload = document.get(field)
        if payload in (None, {}, []):
            document.pop(field, None)
            continue
        if field == "QC" and isinstance(payload, list):
            if len(payload) != 1:
                continue
            payload = payload[0]
        if not isinstance(payload, dict):
            raise ValueError(f"{field} must contain a recorded result object")
        record = deepcopy(payload)
        if record.get("SAMPLE_ID", str(owner)) != str(owner):
            raise ValueError("Embedded RNA result has conflicting ownership")
        record["SAMPLE_ID"] = str(owner)
        record.setdefault("_id", derived_id(owner, collection, field))
        try:
            converted = validate(collection, record)
        except ValidationError as error:
            if field == "QC" and all(item["type"] == "missing" for item in error.errors()):
                # Keep incomplete recorded QC on its sample without manufacturing measurements.
                continue
            raise
        output[collection].append(converted)
        document.pop(field, None)
    return dict(output)


def finish_sample(
    source: Document, document: Document, review: Document
) -> dict[str, list[Document]]:
    """Apply evidence-bound missing metadata, extract history and validate the sample.

    Args:
        source: Unmodified source used to verify the review digest.
        document: Version-specific normalized copy.
        review: Exact source_sha256, missing metadata and optional canonical filters.

    Returns:
        Sample plus all collections derived from its embedded content.

    Raises:
        ValueError: Review is stale, required history is absent or metadata conflicts.
        ValidationError: Destination contracts reject converted content.
    """
    if review.get("source_sha256") != fingerprint(source):
        raise ValueError("Review source_sha256 does not match the original sample")
    if not isinstance(source.get("_id"), ObjectId) or not source.get("time_added"):
        raise ValueError("Original ObjectId and creation timestamp are required")
    unspecified = "legacy" if document.get("asp_id") == "tumwgs" else "base"
    scope = deepcopy(review.get("scope_mapping", {}))
    normalize_scope(scope, unspecified_diagnosis=unspecified)
    if scope:
        if set(scope) - {"asp_group", "diagnosis_id", "reason"} or not scope.get("reason"):
            raise ValueError("Scope mapping accepts asp_group, diagnosis_id and a required reason")
        for key in ("asp_group", "diagnosis_id"):
            if key in scope:
                document[key] = scope[key]
    metadata = deepcopy(review.get("metadata", {}))
    normalize_scope(metadata, unspecified_diagnosis=unspecified)
    normalize_scope(document, unspecified_diagnosis=unspecified)
    allowed = set(COLLECTION_MODEL_ADAPTERS["samples"].json_schema()["properties"]) | {"asp_group"}
    protected = {"_id", "name", "time_added", "latest_report_id", "latest_report_on", "reported"}
    if set(metadata) - (allowed - protected):
        raise ValueError("Metadata may only supply missing canonical sample fields")
    for key, value in metadata.items():
        if document.get(key) is not None and document[key] != value:
            raise ValueError(f"Metadata conflicts with recorded field: {key}")
        document[key] = deepcopy(value)
    for key in (
        "vcf_files",
        "cnv",
        "cov",
        "biomarkers",
        "transloc",
        "fusion_files",
        "expression_path",
        "classification_path",
        "qc",
    ):
        value = document.get(key)
        if isinstance(value, list):
            if len(value) != 1:
                raise ValueError(f"Multiple paths in {key} require a reviewed file mapping")
            document[key] = value[0]
    legacy_filters = [
        key
        for key in document
        if key.startswith(("filter_", "checked_")) or key in {"min_cnv_size", "max_cnv_size"}
    ]
    if legacy_filters or ("filters" in document and document["filters"] is not None):
        if "canonical_filters" not in review:
            raise ValueError("Recorded filters require reviewed canonical_filters")
    if "canonical_filters" in review:
        if not review.get("filters_reason"):
            raise ValueError("Canonical filter mapping requires filters_reason")
        document["filters"] = deepcopy(review["canonical_filters"])
        for key in legacy_filters:
            document.pop(key)
    if not document.get("current_aspc_id"):
        raise ValueError("Supply the exact installed current_aspc_id in metadata")
    if not isinstance(document["current_aspc_id"], ObjectId):
        raise ValueError("current_aspc_id must retain the installed BSON ObjectId")
    normalize_scope(document)
    case = document.setdefault("case", {})
    control = document.get("control") or {}
    if not isinstance(case, dict) or not isinstance(control, dict):
        raise ValueError("Case/control metadata must contain objects")
    for field, nested in (("case_id", case), ("control_id", control)):
        if not document.get(field) and nested.get("id"):
            document[field] = nested["id"]
    if "sample_no" not in document or document["sample_no"] is None:
        document["sample_no"] = 2 if document.get("control_id") else 1
    document.setdefault("paired", bool(document.get("control_id")))
    for old, new in (("clarity-sample-id", "clarity_id"), ("clarity-pool-id", "clarity_pool_id")):
        if old in document:
            value = document.pop(old)
            if new in case and case[new] is not None and case[new] != value:
                raise ValueError(f"Conflicting case {new}")
            case[new] = value
    if "vep_version" in document:
        version = str(document.pop("vep_version"))
        versions = document.setdefault("database_versions", {})
        if "vep" in versions and str(versions["vep"]) != version:
            raise ValueError("Conflicting VEP versions")
        versions["vep"] = version
    result = extract_history(document)
    result["samples"] = [validate("samples", document)]
    return result


def assay_query(assay: str, version: int = 2) -> Document:
    """Select one recorded assay group, including the operator-defined tumwgs split.

    Args:
        assay: Lowercase destination assay identifier.
        version: Source major version; v3 primarily identifies its ASP through assay.

    Returns:
        Read-only samples predicate; groups may be either a string or an array.
    """
    raw = "tumwgs" if assay in {"tumwgs-hema", "tumwgs-solid"} else assay
    query: Document = {"groups": re.compile(f"^{re.escape(raw)}$", re.IGNORECASE)}
    if version == 3:
        pattern = re.compile(f"^{re.escape(assay)}$", re.IGNORECASE)
        return {"$or": [{"assay": pattern}, {"assay": {"$exists": False}, "groups": pattern}]}
    old_assay = next((old for old, current in V2_ASSAY_RENAMES.items() if current == assay), None)
    if old_assay:
        old_pattern = re.compile(f"^{old_assay}$", re.IGNORECASE)
        query = {
            "$or": [
                query,
                {
                    "assay": old_pattern,
                    "groups.1": {"$exists": False},
                    "$or": [{"groups": None}, {"groups": {"$size": 0}}, {"groups": old_pattern}],
                },
            ]
        }
    if assay.startswith("tumwgs-"):
        query["subpanel"] = re.compile(f"^{assay.removeprefix('tumwgs-')}$", re.IGNORECASE)
    elif assay == "tumwgs":
        query["$or"] = [
            {"subpanel": None},
            {"subpanel": re.compile(r"^\s*(?:none|legacy)?\s*$", re.IGNORECASE)},
        ]
    return query


def matches_source(document: Document, assay: str, version: int) -> bool:
    """Match an exported source sample using the same scope as the MongoDB read query.

    Args:
        document: One decoded legacy Extended JSON record.
        assay: Selected lowercase destination assay.
        version: Source major version.

    Returns:
        Whether the recorded assay/group and any tumwgs subpanel match.
    """
    if version == 3 and "assay" in document:
        return str(document["assay"]).lower() == assay
    groups = document.get("groups", [])
    groups = [groups] if isinstance(groups, str) else groups
    raw = "tumwgs" if assay in {"tumwgs-hema", "tumwgs-solid"} else assay
    matches = isinstance(groups, list) and raw in [str(g).lower() for g in groups]
    if version == 2:
        matches = matches or v2_assay_identity(document) == raw
    if assay.startswith("tumwgs-"):
        matches = matches and str(document.get("subpanel", "")).lower() == assay.removeprefix(
            "tumwgs-"
        )
    elif assay == "tumwgs":
        matches = matches and str(document.get("subpanel") or "").strip().lower() in {
            "",
            "none",
            "legacy",
        }
    return bool(matches)


@contextmanager
def source_rows(
    args: argparse.Namespace, version: int, query: Document
) -> Iterator[Iterator[Document]]:
    """Read MongoDB samples or a legacy mongoexport JSON-lines file without source writes.

    Args:
        args: Parsed source, selection and inspection options.
        version: Selects coyote for v2 or coyote3 for v3.
        query: Predicate for a direct MongoDB read.

    Yields:
        Selected source iterator. File-based random inspection uses reservoir sampling.

    Raises:
        ValueError: A source line is malformed or a configured URI is missing.
        PyMongoError: The MongoDB read fails, including unsupported server wire versions.
        OSError: The source export cannot be read.
    """
    if args.input:
        with args.input.open() as stream:
            selected_ids = set(args.sample_id)

            def rows() -> Iterator[Document]:
                """Decode complete Extended JSON lines and apply the selected source scope."""
                for line in stream:
                    if not line.strip():
                        continue
                    row = json_util.loads(line)
                    if not isinstance(row, dict):
                        raise ValueError("Each source line must be one Extended JSON object")
                    if selected_ids and str(row.get("_id")) not in selected_ids:
                        continue
                    if matches_source(row, args.assay_id, version):
                        yield row

            if args.action == "inspect" and not args.all_samples:
                reservoir: list[Document] = []
                random = SystemRandom()
                for index, row in enumerate(rows()):
                    if len(reservoir) < args.random_documents:
                        reservoir.append(row)
                    else:
                        slot = random.randrange(index + 1)
                        if slot < args.random_documents:
                            reservoir[slot] = row
                yield iter(reservoir)
            else:
                yield rows()
        return
    uri = os.environ.get(args.uri_env)
    if not uri:
        raise ValueError(f"Set {args.uri_env} or supply --input")
    database = "coyote" if version == 2 else "coyote3"
    with MongoClient(
        uri, serverSelectionTimeoutMS=5000, appname="coyote-readonly-migration"
    ) as client:
        collection = client[database]["samples"]
        if args.action == "inspect" and not args.all_samples:
            with collection.aggregate(
                [{"$match": query}, {"$sample": {"size": args.random_documents}}],
                maxTimeMS=15000,
            ) as cursor:
                yield iter(cursor)
        else:
            with collection.find(query).batch_size(100) as cursor:
                yield iter(cursor)


def inspect_shapes(documents: list[Document]) -> Document:
    """Describe randomly chosen document structures without returning patient field values.

    Args:
        documents: Bounded random sample loaded through read-only queries.

    Returns:
        Per-document source digests and field-path/type counts across every array item.
        Field names can contain private data; keep this output in protected storage.
    """
    paths: dict[str, Counter] = defaultdict(Counter)

    def visit(value: Any, path: str) -> None:
        """Record value types recursively without recording scalar values."""
        paths[path][type(value).__name__] += 1
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, f"{path}.{key}")
        elif isinstance(value, list):
            for child in value:
                visit(child, f"{path}[]")

    for document in documents:
        visit(document, "$sample")
    return {
        "sampled_documents": len(documents),
        "source_digests": [fingerprint(row) for row in documents],
        "paths": dict(sorted(paths.items())),
    }


def run(version: int, assays: set[str], convert: Callable) -> int:
    """Run a bounded source inspection or prepare validated MongoDB import files.

    Args:
        version: Legacy source version, selecting coyote or coyote3 explicitly.
        assays: Operator-approved destination assay IDs for this source version.
        convert: Version-specific converter accepting a source, review and assay ID.

    Returns:
        Zero on success. This command contains no MongoDB write operation.

    Raises:
        ValueError: Configuration, selected records or conversion is invalid.
        OSError: Protected output cannot be created without overwriting existing files.
        PyMongoError: A read-only source operation fails.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("inspect", "prepare"))
    parser.add_argument("--uri-env", default="MIGRATION_SOURCE_URI")
    parser.add_argument(
        "--input", type=Path, help="Read legacy mongoexport JSON lines instead of MongoDB"
    )
    parser.add_argument("--assay-id", required=True, type=str.lower, choices=sorted(assays))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--random-documents", type=int, default=20)
    parser.add_argument(
        "--all-samples", action="store_true", help="Inspect every sample in this assay"
    )
    parser.add_argument("--review", type=Path)
    parser.add_argument(
        "--case-control-config",
        type=Path,
        help="Reviewed Bjorn/CDM reference connections, field paths and assay mappings",
    )
    parser.add_argument("--sample-id", action="append", default=[])
    args = parser.parse_args()
    if not 1 <= args.random_documents <= 100:
        parser.error("--random-documents must be between 1 and 100")
    if args.action == "prepare" and args.review is None:
        parser.error("prepare requires --review")
    if args.action == "prepare" and args.case_control_config is None:
        parser.error("prepare requires --case-control-config for per-sample Bjorn/CDM enrichment")
    if not args.input and not os.environ.get(args.uri_env):
        parser.error(f"Set {args.uri_env} to the read-only source URI or supply --input")
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    query = assay_query(args.assay_id, version)
    if args.sample_id:
        query["_id"] = {"$in": [ObjectId(value) for value in args.sample_id]}
    database = "coyote" if version == 2 else "coyote3"
    with source_rows(args, version, query) as sources:
        if args.action == "inspect":
            documents = list(sources)
            if not documents:
                raise ValueError("Selection matched no samples")
            (args.output / "structure.json").write_text(
                json.dumps(inspect_shapes(documents), indent=2) + "\n"
            )
            with (args.output / "sampled-source.jsonl").open("x") as stream:
                for row in documents:
                    stream.write(
                        json_util.dumps(row, json_options=json_util.CANONICAL_JSON_OPTIONS) + "\n"
                    )
            template = {
                "samples": {
                    str(row["_id"]): {
                        "source_sha256": fingerprint(row),
                        "metadata": {},
                    }
                    for row in documents
                }
            }
            (args.output / "review-template.json").write_text(
                json_util.dumps(template, indent=2) + "\n"
            )
            print(f"[ok] read-only inspection: {len(documents)} sample structures")
            return 0
        reviews = json_util.loads(args.review.read_text())
        from migrations_scripts.case_control import CaseControlEnricher

        enricher = CaseControlEnricher(args.case_control_config, args.assay_id, args.output)
        counts: Counter = Counter()
        identities: dict[str, set] = defaultdict(set)
        for source in sources:
            review = reviews.get("samples", {}).get(str(source["_id"]), {})
            try:
                converted = convert(source, review, args.assay_id)
                sample, evidence = enricher.enrich(converted["samples"][0])
                converted["samples"] = [sample]
                converted["case_control_sources"] = [evidence]
            except (ValueError, OSError, subprocess.CalledProcessError) as error:
                details = (
                    error.errors(include_input=False, include_context=False, include_url=False)
                    if isinstance(error, ValidationError)
                    else "Read-only reference extraction failed"
                    if isinstance(error, subprocess.CalledProcessError)
                    else str(error)
                )
                (args.output / "failure.json").write_text(
                    json_util.dumps(
                        {
                            "sample_id": source["_id"],
                            "error_type": type(error).__name__,
                            "details": details,
                        },
                        indent=2,
                    )
                    + "\n"
                )
                raise
            for destination, rows in {**converted, "source_samples": [source]}.items():
                for row in rows:
                    if row["_id"] in identities[destination]:
                        raise ValueError(f"Duplicate output identity in {destination}")
                    identities[destination].add(row["_id"])
                    with (args.output / f"{destination}.jsonl").open("a") as stream:
                        stream.write(
                            json_util.dumps(row, json_options=json_util.CANONICAL_JSON_OPTIONS)
                            + "\n"
                        )
                    counts[destination] += 1
        if not counts["samples"]:
            raise ValueError("Selection matched no samples")
        if args.sample_id and counts["samples"] != len(set(args.sample_id)):
            raise ValueError("Some requested samples were absent or outside the selected assay")
    checksums = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in args.output.glob("*.jsonl")
    }
    manifest = {
        "source_version": version,
        "source_database": database,
        "assay_id": args.assay_id,
        "complete": True,
        "counts": dict(counts),
        "sha256": checksums,
        "case_control_config_sha256": hashlib.sha256(
            args.case_control_config.read_bytes()
        ).hexdigest(),
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"[ok] prepared {counts['samples']} samples; no database writes")
    return 0


def command(version: int, assays: set[str], convert: Callable) -> int:
    """Run the CLI while keeping database errors and clinical values out of terminal logs.

    Args:
        version: Legacy major version handled by this entry point.
        assays: Accepted assay identifiers for that source database.
        convert: Source-specific pure converter.

    Returns:
        Zero on completion, one on conversion, filesystem or source-read failure.
        Conversion failure details are stored in the protected output directory.
    """
    try:
        return run(version, assays, convert)
    except (ValueError, OSError, PyMongoError, subprocess.CalledProcessError) as error:
        print(
            f"[failed] {type(error).__name__}; review the protected output and connection settings. No database writes."
        )
        return 1
