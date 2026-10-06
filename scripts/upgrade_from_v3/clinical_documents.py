"""Preserve legacy clinical identities and histories during offline conversion.

Version-specific shapes are normalized before these shared history converters run.
Center-specific sample metadata must be supplied explicitly in the review file.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.contracts.schemas.registry import COLLECTION_MODEL_ADAPTERS
from api.domain.core.annotation_identity import (
    NOMENCLATURE_FIELDS,
    NOMENCLATURE_IDENTITY_FIELD,
    NOMENCLATURE_REQUIRED_FIELDS,
)
from api.domain.core.dna.variant_identity import build_simple_id_hash_from_simple_id

# External references and identity collections are deliberately absent.
CLINICAL_COLLECTIONS = (
    "samples",
    "variants",
    "cnvs",
    "fusions",
    "translocations",
    "biomarkers",
    "pgx",
    "d4_coverage",
    "d4_coverage_blacklist",
    "rna_expression",
    "rna_qc",
    "rna_classification",
    "annotation",
    "anno_vep",
    "reported_variants",
    "sample_comments",
    "finding_comments",
    "reports",
    "blacklist",
)
FINDING_TYPES = {
    "variants": "small_variant",
    "cnvs": "cnv",
    "fusions": "fusion",
    "translocations": "translocation",
}


def validate_document(collection: str, document: dict[str, Any]) -> dict[str, Any]:
    """Validate a converted record, retaining supplied nulls and BSON identifiers.

    Args:
        collection: Canonical application collection name.
        document: Converted document with its original identity.

    Returns:
        Validated persistence fields without invented default timestamps.

    Raises:
        ValueError: Identity is absent or the collection is outside the clinical scope.
        ValidationError: Required target fields or clinical identity constraints fail.
    """
    if collection not in CLINICAL_COLLECTIONS or document.get("_id") is None:
        raise ValueError("Clinical records require an original _id and an allowed collection")
    parsed = COLLECTION_MODEL_ADAPTERS[collection].validate_python(deepcopy(document))
    return parsed.model_dump(mode="python", by_alias=True, exclude_unset=True)


def rename_field(document: dict[str, Any], old: str, new: str) -> None:
    """Move a source field only when an existing target value agrees.

    Args:
        document: Mutable copy of the source document.
        old: Legacy key to remove.
        new: Current key retaining the same value.

    Raises:
        ValueError: Both keys carry different values.
    """
    if old not in document:
        return
    if new in document and document[new] != document[old]:
        raise ValueError(f"Conflicting source and target fields: {old}, {new}")
    document[new] = document.pop(old)


def extract_comments(
    document: dict[str, Any], *, sample: dict[str, Any], finding_type: str | None = None
) -> list[dict[str, Any]]:
    """Extract embedded comments with original IDs, authors, timestamps, and hiding state.

    Args:
        document: Parent document whose comments are removed after extraction.
        sample: Owning sample with preserved BSON identity and name.
        finding_type: Current finding type, or None for sample comments.

    Returns:
        Validated records for the separate comment collection.

    Raises:
        ValueError: Embedded history is not an array of records with stable IDs.
        ValidationError: Comment content does not meet the current contract.
    """
    comments = document.pop("comments", [])
    if not isinstance(comments, list):
        raise ValueError("Embedded comments must be an array")
    records = []
    for comment in comments:
        if not isinstance(comment, dict):
            raise ValueError("Embedded comments must contain documents")
        record = {**comment, "sample_oid": sample["_id"], "sample_name": sample["name"]}
        if finding_type:
            record.update(finding_oid=document["_id"], finding_type=finding_type)
        records.append(
            validate_document("finding_comments" if finding_type else "sample_comments", record)
        )
    return records


def convert_sample(
    source: dict[str, Any], metadata: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Convert a sample and externalize its embedded history before schema validation.

    Args:
        source: Legacy sample after version-specific field normalization.
        metadata: Reviewed canonical fields missing in v3, including explicit assay scope.
            Existing values cannot be overridden; identifiers and history cannot be patched.

    Returns:
        Sample, sample comments, and report references. Saved report content is unchanged.

    Raises:
        ValueError: Metadata conflicts, report counts disagree, or assay mapping is absent.
        ValidationError: The current sample or history contract rejects the converted data.
    """
    document = deepcopy(source)
    if "time_added" not in document:
        raise ValueError("Original sample creation time is required")
    if set(metadata) & {"_id", "name", "comments", "reports", "report_num"}:
        raise ValueError("Migration metadata cannot replace identity or history")
    # v3 assay denotes a user-facing assay group, not necessarily a physical ASP.
    if "assay" in document:
        if "asp_id" not in metadata:
            raise ValueError("Legacy assay requires an explicit physical asp_id mapping")
        document.pop("assay")
    rename_field(document, "profile", "environment")
    rename_field(document, "subpanel", "subpanel_id")
    for key, value in metadata.items():
        if key in document and document[key] != value:
            raise ValueError(f"Reviewed metadata conflicts with source field: {key}")
        document[key] = deepcopy(value)
    # Version provenance is never inferred from the installed pipeline or current date.
    if "vep_version" in document:
        versions = document.setdefault("database_versions", {})
        legacy = document.pop("vep_version")
        if "vep" in versions and str(versions["vep"]) != str(legacy):
            raise ValueError("VEP version provenance conflicts")
        versions["vep"] = str(legacy)
    comments = extract_comments(document, sample=document)
    embedded = document.pop("reports", [])
    if not isinstance(embedded, list):
        raise ValueError("Embedded reports must be an array")
    reports = [
        validate_document(
            "reports",
            {
                **report,
                "sample_oid": document["_id"],
                "sample_name": document["name"],
                "asp_id": document.get("asp_id"),
                "subpanel_id": document.get("subpanel_id"),
                "environment": document.get("environment"),
            },
        )
        for report in embedded
    ]
    numbers = [report["report_num"] for report in reports]
    if len(numbers) != len(set(numbers)):
        raise ValueError("Duplicate embedded report numbers")
    report_num = document.pop("report_num", 0)
    if report_num != max(numbers, default=0):
        raise ValueError("Reported state disagrees with preserved report history")
    if reports:
        latest = max(reports, key=lambda report: report["report_num"])
        document.update(
            reported=True,
            latest_report_id=latest["_id"],
            latest_report_on=latest.get("time_created"),
        )
    document.setdefault("ingested_by", None)
    document.setdefault("ingest_source", None)
    if document.get("ingest_status") != "ready":
        raise ValueError("Reviewed metadata must explicitly confirm ingest_status=ready")
    return validate_document("samples", document), comments, reports


def convert_annotation(source: dict[str, Any]) -> dict[str, Any]:
    """Preserve annotation scope and content while expanding its explicit identity.

    Args:
        source: Legacy classification or narrative with recorded nomenclature and author.

    Returns:
        Current annotation; unknown complementary identities remain null.

    Raises:
        ValueError: Nomenclature is unsupported or populated identity fields conflict.
        ValidationError: Scope, content, or required annotation fields are invalid.
    """
    document = deepcopy(source)
    nomenclature = document.get("nomenclature")
    if nomenclature not in NOMENCLATURE_FIELDS:
        raise ValueError("Unsupported annotation nomenclature")
    if "time_created" not in document:
        raise ValueError("Annotation creation time must be preserved, not invented")
    for key in ("gene", "transcript", "gene1", "gene2"):
        if key not in NOMENCLATURE_FIELDS[nomenclature] and key in document:
            if document[key] is not None:
                raise ValueError("Populated annotation identity requires explicit reconciliation")
            document.pop(key)
    identity = NOMENCLATURE_IDENTITY_FIELD.get(nomenclature)
    if identity:
        if document.get(identity) not in (None, document.get("variant")):
            raise ValueError("Annotation identity conflicts with the recorded variant")
        document[identity] = document["variant"]
    for key in NOMENCLATURE_REQUIRED_FIELDS[nomenclature]:
        document.setdefault(key, None)
    if nomenclature == "g":
        digest = build_simple_id_hash_from_simple_id(document["genomic"])
        if document.get("genomic_hash") not in (None, digest):
            raise ValueError("Annotation genomic hash conflicts with the original identity")
        document["genomic_hash"] = digest
    return validate_document("annotation", document)


def convert_reported_variant(source: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    """Type a v3 DNA small-variant snapshot without recomputing report-time content.

    Args:
        source: Snapshot emitted by v3's DNA variant reporting loop.
        variant: Original small variant referenced by var_oid, used only to check identity.

    Returns:
        Snapshot with explicit SNV analysis and a hash of its preserved identity.

    Raises:
        ValueError: Source finding, sample, or identity differs from the saved snapshot.
        ValidationError: Snapshot fields require a separately reviewed conversion.
    """
    if source.get("var_oid") != variant.get("_id") or str(source.get("sample_oid")) != str(
        variant.get("SAMPLE_ID")
    ):
        raise ValueError("Saved snapshot does not match its original small variant")
    if not source.get("simple_id") or source["simple_id"] != variant.get("simple_id"):
        raise ValueError("Saved snapshot identity differs from its original finding")
    document = deepcopy(source)
    document["analysis_type"] = "SNV"
    document.setdefault("finding_type", "small_variant")
    digest = build_simple_id_hash_from_simple_id(document["simple_id"])
    if document.get("simple_id_hash") not in (None, digest):
        raise ValueError("Saved snapshot identity hash conflicts")
    document["simple_id_hash"] = digest
    return validate_document("reported_variants", document)
