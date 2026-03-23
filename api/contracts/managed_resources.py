"""Single source mapping for managed admin resources.

This registry binds UI schema selectors and DB collection contracts in one place.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ManagedResourceSpec:
    resource: str
    key: str
    collection: str
    schema_type: str
    schema_category: str
    schema_id: str
    contract_version: int = 1


MANAGED_RESOURCE_SPECS: dict[str, ManagedResourceSpec] = {
    "asp": ManagedResourceSpec(
        resource="asp",
        key="asp",
        collection="assay_specific_panels",
        schema_type="asp_schema",
        schema_category="ASP",
        schema_id="asp_schema_contract_v1",
    ),
    "aspc_dna": ManagedResourceSpec(
        resource="aspc",
        key="aspc_dna",
        collection="asp_configs",
        schema_type="asp_config",
        schema_category="DNA",
        schema_id="aspc_schema_contract_dna_v1",
    ),
    "aspc_rna": ManagedResourceSpec(
        resource="aspc",
        key="aspc_rna",
        collection="asp_configs",
        schema_type="asp_config",
        schema_category="RNA",
        schema_id="aspc_schema_contract_rna_v1",
    ),
    "isgl": ManagedResourceSpec(
        resource="isgl",
        key="isgl",
        collection="insilico_genelists",
        schema_type="isgl_config",
        schema_category="ISGL",
        schema_id="isgl_schema_contract_v1",
    ),
    "role": ManagedResourceSpec(
        resource="role",
        key="role",
        collection="roles",
        schema_type="rbac_role",
        schema_category="RBAC_role",
        schema_id="role_schema_contract_v1",
    ),
    "user": ManagedResourceSpec(
        resource="user",
        key="user",
        collection="users",
        schema_type="rbac_user",
        schema_category="RBAC_user",
        schema_id="user_schema_contract_v1",
    ),
    "permission": ManagedResourceSpec(
        resource="permission",
        key="permission",
        collection="permissions",
        schema_type="acl_config",
        schema_category="RBAC",
        schema_id="permission_schema_contract_v1",
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
