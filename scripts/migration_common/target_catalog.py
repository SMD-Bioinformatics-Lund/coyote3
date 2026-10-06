"""Validate installed destination configuration and bind explicitly selected ASPC revisions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.contracts.schemas.registry import COLLECTION_MODEL_ADAPTERS
from scripts.migration_common.offline import digest

CATALOG_COLLECTIONS = (
    "assay_groups",
    "assay_specific_panels",
    "asp_configs",
    "insilico_genelists",
    "subpanels",
    "subpanel_associations",
)


def read_target_catalog(database: Any, *, session: Any = None) -> dict:
    """Read current configuration only; never create collections or indexes."""
    records = {
        name: sorted(database[name].find({}, session=session), key=lambda row: str(row["_id"]))
        for name in CATALOG_COLLECTIONS
    }
    validate_catalog(records)
    return {"format": 1, "sha256": digest(records), "collections": records}


def validate_catalog(records: dict) -> None:
    """Require contract-valid installed configuration with resolvable assay dependencies.

    Args:
        records: Current target collections, including empty arrays for unused resources.

    Raises:
        ValueError: A required collection, identity, or relationship is absent or ambiguous.
        pydantic.ValidationError: An installed record violates its current contract.
    """
    if set(records) != set(CATALOG_COLLECTIONS):
        raise ValueError("Target catalog must include all six configuration collections")
    for name, rows in records.items():
        seen = set()
        for row in rows:
            if row.get("_id") is None or str(row["_id"]) in seen:
                raise ValueError("Target configuration requires unique record identities")
            seen.add(str(row["_id"]))
            COLLECTION_MODEL_ADAPTERS[name].validate_python(row)
    for name in ("assay_groups", "assay_specific_panels", "asp_configs"):
        if not records[name]:
            raise ValueError(f"Install {name} before clinical migration")
    groups = {row["group_id"] for row in records["assay_groups"]}
    assays = {row["asp_id"] for row in records["assay_specific_panels"]}
    for row in records["assay_specific_panels"]:
        if row["asp_group"] not in groups:
            raise ValueError("Installed ASP references a missing assay group")
    for row in records["asp_configs"]:
        if row["asp_id"] not in assays or row["asp_group"] not in groups:
            raise ValueError("Installed ASPC references a missing ASP or assay group")
        validate_scope(records, row["asp_id"], row.get("subpanel_id") or "base")
        validate_genelists(records, row.get("filters", {}))


def validate_scope(records: dict, asp_id: str, subpanel_id: str) -> None:
    """Require a current non-base subpanel definition and its assay association."""
    if subpanel_id == "base":
        return
    definitions = [
        row
        for row in records["subpanels"]
        if row["subpanel_id"] == subpanel_id and row.get("is_current", True)
    ]
    associations = [
        row
        for row in records["subpanel_associations"]
        if row["subpanel_id"] == subpanel_id
        and row["asp_id"] == asp_id
        and row.get("is_current", True)
    ]
    if len(definitions) != 1 or len(associations) != 1:
        raise ValueError("Install an unambiguous subpanel definition and ASP association")


def validate_genelists(records: dict, value: Any) -> None:
    """Reject filter references to gene lists absent from the installed catalog."""
    known = {
        row["isgl_id"]: row for row in records["insilico_genelists"] if row.get("is_active", True)
    }
    if isinstance(value, dict):
        for key, item in value.items():
            if ("genelist" in key or key in {"snvlists", "cnvlists", "fusionlists"}) and isinstance(
                item, list
            ):
                if any(
                    not isinstance(identifier, str) or identifier not in known
                    for identifier in item
                ):
                    raise ValueError("Filter references an ISGL not installed in the target")
                required_type = {"snvlists": "snv", "cnvlists": "cnv", "fusionlists": "fusion"}.get(
                    key
                )
                if required_type and any(
                    required_type not in known[identifier].get("list_type", [])
                    for identifier in item
                ):
                    raise ValueError("Selected ISGL has an incompatible gene-list type")
            validate_genelists(records, item)
    elif isinstance(value, list):
        for item in value:
            validate_genelists(records, item)


def validate_snapshot(catalog: dict) -> dict:
    """Validate a private target snapshot and its content fingerprint."""
    records = catalog.get("collections", {})
    if catalog.get("format") != 1 or catalog.get("sha256") != digest(records):
        raise ValueError("Target catalog fingerprint is invalid")
    validate_catalog(records)
    return records


def bind_sample_review(catalog: dict, original: dict, review: dict) -> dict:
    """Resolve destination context from an explicitly selected installed ASPC revision.

    Args:
        catalog: Validated target snapshot, retained with the migration report.
        original: Unmodified source sample; used to avoid replacing recorded metadata.
        review: Per-sample review containing metadata.current_aspc_id and reconciliation.

    Returns:
        Copied review with missing configuration fields populated from actual target records.
        Historical run, pipeline, counts, authorship, and timestamps are never inferred.

    Raises:
        ValueError: Selection is absent, ambiguous, or disagrees with explicit metadata.
    """
    records = catalog["collections"]
    result = deepcopy(review)
    metadata = result.setdefault("sample", {}).setdefault("metadata", {})
    selected = metadata.get("current_aspc_id", original.get("current_aspc_id"))
    matches = [row for row in records["asp_configs"] if str(row["_id"]) == str(selected)]
    if selected is None or len(matches) != 1:
        raise ValueError("Select one installed ASPC revision using metadata.current_aspc_id")
    aspc = matches[0]
    assays = [
        row
        for row in records["assay_specific_panels"]
        if row["asp_id"] == aspc["asp_id"] and row.get("is_active", True)
    ]
    if len(assays) != 1:
        raise ValueError("Selected ASPC needs one active installed ASP")
    asp = assays[0]
    if asp["asp_group"] != aspc["asp_group"]:
        raise ValueError("Selected ASP and ASPC have different assay groups")
    fields = {
        "current_aspc_id": aspc["_id"],
        "current_aspc_key": aspc["aspc_id"],
        "current_aspc_version": aspc["version"],
        "asp_id": aspc["asp_id"],
        "environment": aspc["environment"],
        "omics_layer": aspc["asp_category"],
        "subpanel_id": aspc.get("subpanel_id") or "base",
    }
    for key, value in fields.items():
        if key in metadata and str(metadata[key]) != str(value):
            raise ValueError(f"Selected ASPC conflicts with reviewed {key}")
        metadata[key] = value
    # Instrument settings are not automatically historical facts. An explicit reviewed
    # mapping may name installed values; missing source fields stay missing otherwise.
    validate_genelists(records, result.get("sample", {}).get("canonical_filters", {}))
    return result


def validate_plan_scope(catalog: dict, plan: dict) -> None:
    """Check migrated sample and shared-resource scopes against installed configuration."""
    records = catalog["collections"]
    groups = {row["group_id"] for row in records["assay_groups"]}
    for name in ("annotation", "blacklist", "d4_coverage_blacklist"):
        for row in plan.get(name, []):
            group = (
                row.get("group")
                if name == "d4_coverage_blacklist"
                else row.get("assay_group", row.get("assay"))
            )
            if group not in groups:
                raise ValueError(f"{name} references an assay group not installed in the target")
            if name == "annotation" and row.get("subpanel") not in (None, "", "base"):
                scope = row["subpanel"]
                assays = {
                    item["asp_id"]
                    for item in records["assay_specific_panels"]
                    if item["asp_group"] == group
                }
                links = [
                    item
                    for item in records["subpanel_associations"]
                    if item["subpanel_id"] == scope
                    and item["asp_id"] in assays
                    and item.get("is_current", True)
                ]
                if not links:
                    raise ValueError(
                        "Annotation subpanel has no installed association in its assay group"
                    )
                for link in links:
                    validate_scope(records, link["asp_id"], scope)
    for row in plan.get("samples", []):
        validate_scope(records, row["asp_id"], row.get("subpanel_id") or "base")
        validate_genelists(records, row.get("filters", {}))
