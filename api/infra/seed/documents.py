"""Assemble validated installation catalogs with explicit actor provenance."""

from datetime import datetime, timezone
from pathlib import Path

from api.application.reporting.clinical_rules.validation import content_hash
from api.application.resources.release_compilation import compile_bundle_configurations
from api.contracts.schemas.clinical_rules import ClinicalRuleSetDoc
from api.contracts.schemas.registry import normalize_collection_document
from api.infra.seed.bundle import (
    canonicalize_seed_contract,
    load_reference_seed_pack,
    lower_business_keys,
    stamp_docs,
)
from api.infra.seed.query_rules import prepare_query_rule_seeds

BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2] / "config" / "bootstrap"
DEFAULT_RBAC_DIR = BOOTSTRAP_ROOT / "rbac"
DEFAULT_REFERENCE_DIR = BOOTSTRAP_ROOT / "reference"


def build_seed_documents(
    *,
    rbac_dir: Path,
    reference_dir: Path,
    actor: str,
    include_knowledgebase: bool = True,
) -> dict[str, list[dict]]:
    """Prepare system catalogs as first versions attributed to the initial administrator.

    Args:
        rbac_dir: Directory containing bundled permission and role definitions.
        reference_dir: Directory containing bundled reference snapshots.
        actor: Normalized username of the system administrator created at installation.
        include_knowledgebase: Load bundled HGNC/VEP snapshots when explicitly requested.

    Returns:
        Validated documents with fresh audit timestamps and initial document versions.
        Reference release identifiers and clinical content are preserved.

    Raises:
        ValueError: Seed normalization or collection validation fails.
        OSError: A selected seed file cannot be read.
    """
    payload = load_reference_seed_pack(rbac_dir)
    payload.update(
        load_reference_seed_pack(reference_dir, include_knowledgebase=include_knowledgebase)
    )

    canonicalize_seed_contract(payload)
    lower_business_keys(payload)
    installed_at = datetime.now(timezone.utc).isoformat()
    stamp_docs(payload, actor, installed_at)
    payload["query_rule_sets"] = prepare_query_rule_seeds(
        payload.get("query_rule_sets", []), payload.get("assay_groups", []), actor=actor
    )

    for collection in (
        "assay_groups",
        "permissions",
        "roles",
        "assay_specific_panels",
        "asp_configs",
        "insilico_genelists",
    ):
        for document in payload.get(collection, []):
            document["system_managed"] = True
            document["version"] = 1
            document["updated_by"] = actor
            document["updated_on"] = installed_at

    for document in payload.get("clinical_rule_sets", []):
        document["system_installed"] = True
        document["content_version"] = 1
        document["revision"] = 1
        for field in ("published_by", "retired_by"):
            if document.get(field) is not None:
                document[field] = actor
        for field in ("published_at", "effective_from", "retired_at"):
            if document.get(field) is not None:
                document[field] = installed_at
        review = document.get("review", {})
        for field in ("submitted_by", "clinical_reviewer", "publisher"):
            if review.get(field) is not None:
                review[field] = actor
        for field in ("submitted_at", "clinical_decision_at"):
            if review.get(field) is not None:
                review[field] = installed_at
        for event in document.get("lifecycle", []):
            event["actor"] = actor
            event["occurred_at"] = installed_at
        document["content_hash"] = content_hash(ClinicalRuleSetDoc.model_validate(document))

    normalized: dict[str, list[dict]] = {}
    for collection, documents in payload.items():
        normalized[collection] = [
            normalize_collection_document(collection, document) for document in documents
        ]
    compile_bundle_configurations(normalized)
    return normalized
