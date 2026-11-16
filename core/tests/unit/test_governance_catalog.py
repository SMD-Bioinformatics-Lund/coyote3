"""Shared permission definitions are available without the API or a database."""

import pytest
from coyote.config import governance_catalog
from coyote.config.governance_catalog import load_governance_catalog
from coyote.contracts.schemas.registry import normalize_collection_document


def test_shipped_roles_reference_unique_valid_core_permission_definitions():
    """Every factory grant has one canonical definition accepted by core contracts."""
    permissions = load_governance_catalog("permissions")
    roles = load_governance_catalog("roles")
    identifiers = [item["permission_id"] for item in permissions]
    assert identifiers and len(set(identifiers)) == len(identifiers)
    assert {"sample:view", "report:preview"} <= set(identifiers)
    role_ids = [item["role_id"] for item in roles]
    assert role_ids and len(set(role_ids)) == len(role_ids)
    for role in roles:
        assert set(role["permissions"]) <= set(identifiers)
    for name, documents in (("permissions", permissions), ("roles", roles)):
        for document in documents:
            normalize_collection_document(name, document)


def test_catalog_reads_do_not_share_mutable_grants_or_installation_metadata():
    """Preparing deployment records cannot change the next host's factory baseline."""
    initial = load_governance_catalog("roles")
    baseline = load_governance_catalog("roles")
    initial[0]["permissions"].append("synthetic:test")
    initial[0]["created_by"] = "synthetic-installer"
    assert load_governance_catalog("roles") == baseline


@pytest.mark.parametrize("payload", ["[]\n", '"permission"\n', "{invalid}\n"])
def test_catalog_rejects_invalid_document_shapes(monkeypatch, tmp_path, payload):
    """Malformed package data fails before an installer receives documents to write."""
    monkeypatch.setattr(governance_catalog, "RBAC_CATALOG_DIR", tmp_path)
    (tmp_path / "permissions.seed.ndjson").write_text(payload)
    with pytest.raises(ValueError):
        load_governance_catalog("permissions")


def test_catalog_blank_lines_do_not_create_documents(monkeypatch, tmp_path):
    monkeypatch.setattr(governance_catalog, "RBAC_CATALOG_DIR", tmp_path)
    (tmp_path / "permissions.seed.ndjson").write_text('\n{"permission_id":"synthetic:test"}\n\n')
    assert load_governance_catalog("permissions") == [{"permission_id": "synthetic:test"}]
