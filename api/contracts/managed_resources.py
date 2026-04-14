"""Single source mapping for managed resource forms and collection contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ManagedResourceSpec:
    resource: str
    key: str
    collection: str
    form_type: str
    form_category: str
    contract_version: int = 1


MANAGED_RESOURCE_SPECS: dict[str, ManagedResourceSpec] = {
    "asp": ManagedResourceSpec(
        resource="asp",
        key="asp",
        collection="assay_specific_panels",
        form_type="asp",
        form_category="ASP",
    ),
    "aspc_dna": ManagedResourceSpec(
        resource="aspc",
        key="aspc_dna",
        collection="asp_configs",
        form_type="asp_config",
        form_category="DNA",
    ),
    "aspc_rna": ManagedResourceSpec(
        resource="aspc",
        key="aspc_rna",
        collection="asp_configs",
        form_type="asp_config",
        form_category="RNA",
    ),
    "isgl": ManagedResourceSpec(
        resource="isgl",
        key="isgl",
        collection="insilico_genelists",
        form_type="isgl",
        form_category="ISGL",
    ),
    "role": ManagedResourceSpec(
        resource="role",
        key="role",
        collection="roles",
        form_type="role",
        form_category="RBAC_role",
    ),
    "user": ManagedResourceSpec(
        resource="user",
        key="user",
        collection="users",
        form_type="user",
        form_category="RBAC_user",
    ),
    "permission": ManagedResourceSpec(
        resource="permission",
        key="permission",
        collection="permissions",
        form_type="permission",
        form_category="RBAC",
    ),
}


def managed_resource_spec(key: str) -> ManagedResourceSpec:
    """Return managed resource spec by key."""
    spec = MANAGED_RESOURCE_SPECS.get(key)
    if not spec:
        raise KeyError(f"Unknown managed resource key: {key}")
    return spec


def aspc_spec_for_category(category: str) -> ManagedResourceSpec:
    """Return ASPC spec for DNA/RNA category."""
    normalized = str(category or "DNA").strip().upper()
    if normalized == "RNA":
        return MANAGED_RESOURCE_SPECS["aspc_rna"]
    return MANAGED_RESOURCE_SPECS["aspc_dna"]
