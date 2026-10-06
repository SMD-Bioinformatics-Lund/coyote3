"""Convert versioned clinical exports without selecting new clinical interpretations."""

from __future__ import annotations

import math
from copy import deepcopy
from pathlib import Path

from api.application.ingest.parsers import _parse_transcripts
from api.config.constants import ALL_SAMPLE_FILE_KEYS
from api.contracts.schemas.dna import VariantCsqDoc
from api.domain.core.dna.variant_identity import build_simple_id_hash_from_simple_id
from scripts.migration_common.clinical_plan import build_plan
from scripts.migration_common.offline import (
    SAMPLE_COLLECTIONS,
    RecordConversionError,
    SourceIndex,
    digest,
)
from scripts.upgrade_from_v3.clinical_documents import (
    convert_annotation,
    rename_field,
    validate_document,
)


def supplement(source: dict, review: dict | None) -> dict:
    """Add reviewed missing fields, bound to the exact original record digest.

    Args:
        source: Original BSON record, which is never mutated.
        review: Optional source_sha256, reason, and fields mapping of dotted paths.
            Existing nonnull values cannot be overwritten, including clinical values.

    Returns:
        A copy with reviewed missing fields supplied.

    Raises:
        ValueError: Evidence is stale, attribution is absent, or a value would be overwritten.
    """
    document = deepcopy(source)
    if review is None:
        return document
    if review.get("source_sha256") != digest(source) or not review.get("reason"):
        raise ValueError("Reconciliation requires a matching source digest and reason")
    for path, value in review.get("fields", {}).items():
        parts = path.split(".")
        if any(not part or part.startswith("$") for part in parts) or parts[0] == "_id":
            raise ValueError("Invalid reconciliation field")
        parent = document
        for part in parts[:-1]:
            if parent.get(part) is None:
                parent[part] = {}
            if not isinstance(parent[part], dict):
                raise ValueError("Reconciliation path crosses a non-document value")
            parent = parent[part]
        if parent.get(parts[-1]) is not None and parent[parts[-1]] != value:
            raise ValueError("Reconciliation cannot overwrite recorded values")
        parent[parts[-1]] = deepcopy(value)
    return document


def prepare_sample(source: dict, review: dict) -> tuple[dict, dict]:
    """Translate file registrations and require explicit assay, filter, and platform mapping.

    Args:
        source: Original sample, including embedded history.
        review: Per-sample metadata plus optional missing-field supplements and reviewed
            canonical_filters. Filter replacement requires filters_source_sha256 and reason.

    Returns:
        Sample ready for history extraction, and explicit destination metadata.
    """
    document = supplement(source, review.get("supplement"))
    metadata = deepcopy(review.get("metadata", {}))
    if "sequencing_technology" in document:
        if not metadata.get("platform") or not metadata.get("read_mode"):
            raise ValueError("Legacy sequencing technology needs reviewed platform/read_mode")
        document.pop("sequencing_technology")
    legacy_filters = {
        key: value
        for key, value in source.items()
        if key == "filters" or key.startswith("filter_") or key.startswith("checked_")
    }
    if legacy_filters or "canonical_filters" in review:
        if (
            "canonical_filters" not in review
            or review.get("filters_source_sha256") != digest(legacy_filters)
            or not review.get("filters_reason")
        ):
            raise ValueError("Stored filters require an explicit reviewed canonical filter profile")
        for key in legacy_filters:
            document.pop(key, None)
        document["filters"] = deepcopy(review["canonical_filters"])
    files = deepcopy(document.get("files", {}))
    registration = review.get("file_registration")
    if registration is not None:
        legacy_paths = {key: source[key] for key in ALL_SAMPLE_FILE_KEYS if key in source}
        if (
            registration.get("source_sha256") != digest(legacy_paths)
            or not registration.get("reason")
            or not registration.get("files")
        ):
            raise ValueError("File reconciliation requires original path digest and evidence")
        if files and files != registration["files"]:
            raise ValueError("File reconciliation cannot replace existing canonical registrations")
        files = deepcopy(registration["files"])
    for key in ALL_SAMPLE_FILE_KEYS:
        if key not in document:
            continue
        value = document.pop(key)
        if registration is not None:
            continue
        if isinstance(value, list):
            if len(value) != 1:
                raise ValueError(
                    "Multiple legacy file paths require an explicit file reconciliation"
                )
            value = value[0]
        if value in (None, ""):
            continue
        if not isinstance(value, str):
            raise ValueError("Legacy file registration is not a path string")
        if key in files and files[key].get("path") != value:
            raise ValueError("Legacy and canonical file paths disagree")
        files.setdefault(key, {"path": value})
    if files:
        document["files"] = files
    for old, new in (
        ("clarity-sample-id", "clarity_id"),
        ("clarity-pool-id", "clarity_pool_id"),
        ("bam", "bam"),
    ):
        if old in document:
            value = document.pop(old)
            case = document.setdefault("case", {})
            if new in case and case[new] != value:
                raise ValueError("Top-level and case metadata disagree")
            case[new] = value
    for report in document.get("reports", []):
        # V2 has a stable BSON report identity but no string ID or display name.
        # These are deterministic destination identifiers, not historical report metadata.
        if report.get("_id") is not None:
            report.setdefault("report_id", str(report["_id"]))
        if report.get("filepath"):
            report.setdefault("report_name", Path(report["filepath"]).name)
    return document, metadata


def normalize_csq(source: dict) -> dict:
    """Convert numeric VEP scalar labels to text while preserving transcript selection."""
    result = deepcopy(source)
    for key, field in VariantCsqDoc.model_fields.items():
        if key not in {"Consequence", "CLIN_SIG"} and key in result:
            if isinstance(result[key], (int, float)) and not isinstance(result[key], bool):
                result[key] = str(result[key])
    return result


def recorded_frequency(value: object, allele: str) -> float | None:
    """Read numeric or allele-labelled VEP frequencies without treating missing as zero.

    Args:
        value: Recorded scalar or ampersand-separated values from the first consequence.
        allele: Finding ALT allele for fields containing explicit allele labels.

    Returns:
        Maximum recorded applicable frequency, including zero, or None when absent.

    Raises:
        ValueError: A supplied frequency is malformed, nonfinite, or outside [0, 1].
    """
    if value is None or value in ("", ".", "NA", "N/A"):
        return None
    frequencies = []
    for token in str(value).split("&"):
        if ":" in token:
            label, token = token.split(":", 1)
            if label != allele:
                continue
        if token in ("", ".", "NA", "N/A"):
            continue
        try:
            number = float(token)
        except ValueError:
            raise ValueError("Recorded population frequency requires reconciliation") from None
        if not math.isfinite(number) or not 0 <= number <= 1:
            raise ValueError("Recorded population frequency is outside [0, 1]")
        frequencies.append(number)
    return max(frequencies) if frequencies else None


def prepare_finding(collection: str, source: dict, review: dict | None = None) -> dict:
    """Normalize recorded finding shapes without rerunning annotation or classification.

    Args:
        collection: Canonical destination name.
        source: Original record with preserved identity and sample association.
        review: Optional digest-bound additions for absent required fields.

    Returns:
        A copied record for target-contract validation.

    Raises:
        ValueError: A transcript selection, biomarker unit, or required meaning is unknown.
    """
    document = supplement(source, review)
    for key in ("CHROM", "chr"):
        if isinstance(document.get(key), (int, float)):
            document[key] = str(document[key])
    if isinstance(document.get("FILTER"), str):
        document["FILTER"] = document["FILTER"].split(";")
    if document.get("QUAL") in (".", ""):
        document["QUAL"] = None
    if collection == "variants":
        info = document["INFO"]
        consequences = info.get("CSQ", [])
        if not isinstance(consequences, list) or not consequences:
            raise ValueError("Original transcript consequences are required")
        if not info.get("selected_CSQ"):
            selected = [
                row
                for row in consequences
                if document.get("selected_csq_feature")
                and row.get("Feature") == document["selected_csq_feature"]
            ]
            if len(selected) != 1:
                raise ValueError(
                    "No unique historical transcript selection; reviewed input required"
                )
            info["selected_CSQ"] = deepcopy(selected[0])
            info["selected_CSQ_criteria"] = "preserved_legacy_selected_csq_feature"
        if not info.get("selected_CSQ_criteria"):
            raise ValueError("Transcript selection provenance is required")
        info["CSQ"] = [normalize_csq(row) for row in consequences]
        info["selected_CSQ"] = normalize_csq(info["selected_CSQ"])
        if info["selected_CSQ"] not in info["CSQ"]:
            raise ValueError("Selected consequence is not present in original transcript evidence")
        aggregates = _parse_transcripts(info["CSQ"])
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
            document.setdefault(key, [value] if key == "hotspots" else value)
        document.setdefault("variant_class", info["CSQ"][0].get("VARIANT_CLASS"))
        document.setdefault("selected_csq_feature", info["selected_CSQ"].get("Feature"))
        first = info["CSQ"][0]
        for destination, source_fields in {
            "gnomad_frequency": ("gnomAD_AF", "gnomADg_AF"),
            "gnomad_max": ("MAX_AF",),
            "exac_frequency": ("ExAC_MAF",),
            "thousandG_frequency": ("GMAF",),
        }.items():
            if destination not in document:
                values = [
                    recorded_frequency(first.get(key), document["ALT"]) for key in source_fields
                ]
                document[destination] = next((value for value in values if value is not None), None)
        document.setdefault(
            "simple_id", "_".join(str(document[key]) for key in ("CHROM", "POS", "REF", "ALT"))
        )
        if document.get("simple_id_hash") is None:
            document["simple_id_hash"] = build_simple_id_hash_from_simple_id(document["simple_id"])
    elif collection == "cnvs":
        if document.get("ratio") is not None:
            try:
                ratio = float(document["ratio"])
            except (ValueError, TypeError):
                raise ValueError("CNV ratio is not a recorded numeric measurement") from None
            if not math.isfinite(ratio):
                raise ValueError("CNV ratio must be finite")
    elif collection == "translocations":
        info = document["INFO"]
        if isinstance(info.get("PANEL"), str):
            info["PANEL"] = info["PANEL"].split("|")
        for genotype in document.get("GT", []):
            rename_field(genotype, "_sample_id", "sample")
    elif collection == "biomarkers":
        for key in ("MSIS", "MSIP"):
            if isinstance(document.get(key), dict):
                rename_field(document[key], "perc", "per")
        if "biomarker" in document:
            # A scalar metric does not establish units or a complete HRD/MSI result.
            label = str(document["biomarker"]).upper()
            typed_key = {"TMB": "TMB", "HRD": "HRD", "MSIS": "MSIS", "MSIP": "MSIP"}.get(label)
            if not typed_key or not document.get(typed_key):
                raise ValueError("Scalar biomarker needs an explicit typed measurement and unit")
            metric = {"TMB": "value", "HRD": "sum", "MSIS": "per", "MSIP": "per"}[typed_key]
            if document.get("value") != document[typed_key].get(metric):
                raise ValueError("Scalar and typed biomarker values disagree")
            if typed_key == "TMB" and document[typed_key].get("unit") != "mut/Mb":
                raise ValueError("Legacy scalar TMB requires an explicitly verified unit")
    return document


def sample_plan(source: SourceIndex, sample_id: str, review: dict) -> dict[str, list[dict]]:
    """Build one complete sample bundle, preserving related histories and snapshot links.

    Args:
        source: Prepared read-only export index of the selected major version.
        sample_id: Original BSON sample identity as text.
        review: Mapping with sample, records, and optional coverage reconciliation.

    Returns:
        Validated destination collections, including referenced clinical annotations.

    Raises:
        ValueError: A clinical dependency is missing, ambiguous, or not reconciled.
    """
    original = source.get("samples", sample_id)
    sample, metadata = prepare_sample(original, review.get("sample", {}))
    documents = {"samples": [sample]}
    for physical, canonical in SAMPLE_COLLECTIONS[source.version].items():
        documents[canonical] = []
        for row in source.rows(physical, sample_id):
            try:
                converted = prepare_finding(
                    canonical, row, review.get("records", {}).get(physical, {}).get(str(row["_id"]))
                )
                if canonical != "reported_variants":
                    validate_document(canonical, converted)
                documents[canonical].append(converted)
            except (ValueError, TypeError, KeyError) as error:
                raise RecordConversionError(physical, row, error) from error
    annotation_ids = {
        str(row[key])
        for row in documents.get("reported_variants", [])
        for key in ("annotation_oid", "annotation_text_oid")
        if row.get(key)
    }
    documents["annotation"] = [
        supplement(
            source.get("annotation", identity),
            review.get("records", {}).get("annotation", {}).get(identity),
        )
        for identity in sorted(annotation_ids)
    ]
    coverage = list(source.rows("coverage", sample_id))
    if coverage:
        decision = review.get("coverage", {})
        if (
            decision.get("source_sha256") != digest(coverage)
            or not decision.get("reason")
            or decision.get("action") not in {"archive_only", "replace"}
        ):
            raise ValueError("Legacy interval coverage requires an explicit reconciliation")
        if decision["action"] == "replace":
            replacement = decision.get("panel_coverage", [])
            if not replacement:
                raise ValueError("Replacement coverage cannot be empty")
            documents.setdefault("panel_coverage", []).extend(replacement)
    plan = build_plan(documents, {sample_id: metadata})
    comments = {str(row["_id"]) for row in plan.get("sample_comments", [])}
    for snapshot in plan.get("reported_variants", []):
        if (
            snapshot.get("sample_comment_oid")
            and str(snapshot["sample_comment_oid"]) not in comments
        ):
            raise ValueError("Saved finding references an absent sample comment")
    return plan


def independent_plan(source: SourceIndex, kind: str, review: dict) -> dict[str, list[dict]]:
    """Convert shared annotations or blacklist entries independently of sample batches."""
    documents = []
    for original in source.rows(kind):
        try:
            record = supplement(original, review.get(str(original["_id"])))
            if kind == "annotation":
                record = convert_annotation(record)
            elif kind == "blacklist":
                rename_field(record, "assay", "assay_group")
                record = validate_document(kind, record)
            else:
                raise ValueError("Unsupported independent clinical resource")
        except (ValueError, TypeError, KeyError) as error:
            raise RecordConversionError(kind, original, error) from error
        documents.append(record)
    return {kind: documents}
