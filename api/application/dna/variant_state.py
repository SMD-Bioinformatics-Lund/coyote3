"""State-changing and lookup helpers for DNA variant workflows."""

from __future__ import annotations

from api.contracts.operations import OperationResult
from api.domain.common.errors import api_error


def require_variant_for_sample(service, *, sample: dict, var_id: str) -> dict:
    """Load a variant and assert it belongs to the provided sample."""
    variant = service.variant_repository.get_variant(var_id)
    if not variant or str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
        raise api_error(404, "Variant not found for sample")
    return variant


def set_variant_bulk_flag(
    service, *, sample: dict, resource_ids: list[str], apply: bool, flag: str
) -> OperationResult:
    """Apply a bulk flag with the authorized sample in the database predicate."""
    fields = {"false_positive": "fp", "irrelevant": "irrelevant"}
    if flag not in fields:
        raise ValueError(f"Unsupported flag: {flag}")
    return service.variant_repository.set_sample_finding_flag(
        sample_id=str(sample["_id"]), resource_ids=resource_ids, flag=fields[flag], value=apply
    )


def blacklist_variant(service, *, variant: dict[str, str], assay_group: str) -> None:
    """Create a blacklist entry for a variant in an assay group."""
    return service.blacklist_repository.blacklist_variant(variant, assay_group)


def set_variant_comment_hidden(service, *, var_id: str, comment_id: str, hidden: bool) -> None:
    """Hide or unhide a variant comment."""
    if hidden:
        service.variant_repository.hide_var_comment(var_id, comment_id)
        return
    service.variant_repository.unhide_variant_comment(var_id, comment_id)


def coerce_bool(value: object, default: bool = True) -> bool:
    """Convert arbitrary input into a boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return default
