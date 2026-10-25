"""Ingestion authorization shared by local application operations and HTTP adapters."""

from typing import Any

from coyote3.application.common.access import enforce_access
from coyote3.application.operations.runtime import ApplicationRuntime
from coyote3.domain.common.errors import api_error

_COLLECTION_CREATE_PERMISSION_MAP: dict[str, str] = {
    "users": "user:create",
    "roles": "role:create",
    "permissions": "permission.policy:create",
    "assay_specific_panels": "assay.panel:create",
    "asp_configs": "assay.config:create",
    "insilico_genelists": "gene_list.insilico:create",
}

_COLLECTION_UPDATE_PERMISSION_MAP: dict[str, str] = {
    "users": "user:edit",
    "roles": "role:edit",
    "permissions": "permission.policy:edit",
    "assay_specific_panels": "assay.panel:edit",
    "asp_configs": "assay.config:edit",
    "insilico_genelists": "gene_list.insilico:edit",
}

_SAMPLE_LINKED_COLLECTIONS: frozenset[str] = frozenset(
    {
        "samples",
        "sample_comments",
        "finding_comments",
        "reports",
        "variants",
        "cnvs",
        "translocations",
        "biomarkers",
        "d4_coverage",
        "fusions",
        "rna_expression",
        "rna_classification",
        "rna_qc",
        "reported_variants",
        "d4_coverage_blacklist",
    }
)


def _is_superuser(user: Any) -> bool:
    """Read superuser status, defaulting to False when the attribute is absent.

    Args:
        user: User object whose is_superuser attribute is inspected.

    Returns:
        The attribute's truth value, or False if it is missing.
    """
    return bool(getattr(user, "is_superuser", False))


def enforce_collection_permission(
    runtime: ApplicationRuntime, *, user: Any, collection: str, action: str
) -> None:
    """Enforce collection-level action permissions for non-superuser operators."""
    if collection in {"configuration_profiles", "configuration_promotions"}:
        raise api_error(
            status_code=403,
            message="Use the configuration authoring and independent publication workflows.",
        )
    if _is_superuser(user):
        return
    if (
        collection in {"users", "roles", "permissions"}
        or collection in _SAMPLE_LINKED_COLLECTIONS
        or collection == "annotation"
    ):
        raise api_error(
            status_code=403,
            message="Direct identity or clinical collection ingest requires a superuser; use the dedicated workflow.",
        )
    if action == "create":
        permission = _COLLECTION_CREATE_PERMISSION_MAP.get(collection)
    elif action == "update":
        permission = _COLLECTION_UPDATE_PERMISSION_MAP.get(collection)
    else:
        permission = None
    if not permission and collection in _SAMPLE_LINKED_COLLECTIONS:
        permission = "sample:edit:own"
    if permission:
        enforce_access(user, permission=permission, policy_factory=runtime.policy_factory)


def enforce_sample_ingest_permission(
    runtime: ApplicationRuntime, user: Any, payload: dict[str, Any] | None = None
) -> None:
    """Require sample:edit:own for non-superuser operators."""
    if _is_superuser(user):
        return
    if payload is not None and (not payload.get("asp_id") or not payload.get("environment")):
        raise api_error(400, "Scoped sample ingest requires asp_id and environment.")
    context = (
        None
        if payload is None
        else {
            "asp_id": payload.get("asp_id"),
            "environment": payload.get("environment"),
        }
    )
    enforce_access(
        user, permission="sample:edit:own", context=context, policy_factory=runtime.policy_factory
    )
