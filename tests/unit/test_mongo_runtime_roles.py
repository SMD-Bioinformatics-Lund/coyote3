"""Collection-scoped runtime permissions and identity role provisioning."""

import json

import pytest

from api.infra.security.mongo_roles import (
    identity_role,
    runtime_roles,
    verify_runtime_audit_permissions,
)
from scripts.database.manage_mongo_roles import POLICY, policy_text, runtime_principal


def test_runtime_role_cannot_change_or_drop_clinical_audit_records():
    role = identity_role("synthetic_identity")
    protected = next(
        item for item in role["privileges"] if item["resource"]["collection"] == "audit_events"
    )
    assert set(protected["actions"]) == {"find", "insert", "listIndexes"}
    assert not role["roles"]
    assert all(item["resource"]["db"] == "synthetic_identity" for item in role["privileges"])
    assert POLICY.read_text() == policy_text()
    manifest = json.loads(POLICY.read_text())
    cursor = next(
        index for index in manifest["indexes"] if index["name"] == "idx_audit_notification_cursor"
    )
    assert cursor["fields"] == [["source.environment", 1], ["occurred_at", 1], ["_id", 1]]


def test_identity_role_upgrade_does_not_grant_other_deployments_database_permissions():
    config = {
        "COYOTE3_MONGO_URI": "mongodb://primary/?replicaSet=app",
        "IDENTITY_MONGO_URI": "mongodb://identity/?replicaSet=identity",
        "KNOWLEDGEBASE_MONGO_URI": "mongodb://kb/?replicaSet=kb",
        "BAM_MONGO_URI": "mongodb://bam/?replicaSet=bam",
        "COYOTE3_DB": "clinical",
        "IDENTITY_DB": "clinical",
        "KNOWLEDGEBASE_DB": "references",
        "BAM_DB": "alignments",
    }
    assert runtime_roles(config) == [{"role": "coyote3_runtime_identity", "db": "clinical"}]


@pytest.mark.parametrize(
    "uri,authentication_database",
    [
        (
            "mongodb://synthetic%2Duser@identity/runtime-auth?authSource=explicit-auth",
            "explicit-auth",
        ),
        ("mongodb://synthetic%2Duser@identity/runtime-auth", "runtime-auth"),
        ("mongodb://synthetic%2Duser@identity", "admin"),
    ],
)
def test_installer_selects_the_configured_runtime_principal(uri, authentication_database):
    config = {
        "COYOTE3_MONGO_URI": "mongodb://primary",
        "IDENTITY_MONGO_URI": uri,
        "COYOTE3_DB": "clinical",
        "IDENTITY_DB": "identity",
        "KNOWLEDGEBASE_DB": "references",
        "BAM_DB": "alignments",
    }
    assert runtime_principal(config) == ("synthetic-user", authentication_database)


@pytest.mark.parametrize(
    "maintenance_user,success", [("synthetic-admin", True), ("runtime", False)]
)
def test_role_upgrade_uses_inferred_runtime_user_and_cannot_replace_maintenance_principal(
    monkeypatch, maintenance_user, success, capsys
):
    from unittest.mock import MagicMock, Mock

    from scripts.database import manage_mongo_roles

    for key, value in {
        "COYOTE3_MONGO_URI": "mongodb://runtime@synthetic/?replicaSet=rs",
        "COYOTE3_DB": "clinical",
        "IDENTITY_DB": "identity",
        "KNOWLEDGEBASE_DB": "references",
        "BAM_DB": "alignments",
        "SYNTHETIC_MAINTENANCE_URI": "mongodb://maintenance@synthetic/?replicaSet=rs",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("IDENTITY_MONGO_URI", raising=False)
    monkeypatch.delenv("KNOWLEDGEBASE_MONGO_URI", raising=False)
    monkeypatch.delenv("BAM_MONGO_URI", raising=False)
    client = MagicMock()
    auth = client.__getitem__.return_value
    auth.command.return_value = {"users": [{"user": "runtime"}]}
    client.admin.command.return_value = {
        "authInfo": {
            "authenticatedUsers": [
                {"user": maintenance_user, "db": "admin"},
            ]
        }
    }
    factory = MagicMock()
    factory.return_value.__enter__.return_value = client
    provision = Mock()
    monkeypatch.setattr(manage_mongo_roles, "MongoClient", factory)
    monkeypatch.setattr(manage_mongo_roles, "provision_identity", provision)
    monkeypatch.setattr(
        "sys.argv",
        ["manage_mongo_roles", "--maintenance-uri-env", "SYNTHETIC_MAINTENANCE_URI", "--apply"],
    )
    assert manage_mongo_roles.main() == (0 if success else 1)
    updates = [call for call in auth.command.call_args_list if call.args[0] == "updateUser"]
    if success:
        provision.assert_called_once()
        assert updates[0].args == ("updateUser", "runtime")
    else:
        provision.assert_not_called()
        assert not updates
    output = capsys.readouterr()
    assert "mongodb://" not in output.out + output.err


@pytest.mark.parametrize(
    "resource",
    [
        {"db": "identity", "collection": "audit_events"},
        {"db": "identity", "collection": ""},
        {"db": "", "collection": ""},
        {"anyResource": True},
    ],
)
def test_preflight_rejects_effective_destructive_audit_grants(resource):
    from types import SimpleNamespace

    client = SimpleNamespace(
        admin=SimpleNamespace(
            command=lambda *args, **kwargs: {
                "authInfo": {
                    "authenticatedUsers": [{"user": "synthetic"}],
                    "authenticatedUserPrivileges": [{"resource": resource, "actions": ["remove"]}],
                }
            }
        )
    )
    with pytest.raises(ValueError, match="alter retained audit history"):
        verify_runtime_audit_permissions(client, "identity")


def test_unauthenticated_identity_warns_and_proceeds_without_mutating_data(caplog):
    """A center may run without MongoDB authentication while application RBAC remains active."""
    from unittest.mock import MagicMock

    client = MagicMock()
    client.admin.command.return_value = {"authInfo": {"authenticatedUsers": []}}
    verify_runtime_audit_permissions(client, "identity")
    assert "unauthenticated" in caplog.text
    assert "continuing" in caplog.text
    client.__getitem__.assert_not_called()


def test_disabled_mongodb_authorization_warns_instead_of_blocking(caplog):
    """Credentials on a server without enforced authorization do not protect audit history."""
    from unittest.mock import MagicMock

    client = MagicMock()
    client.admin.command.return_value = {
        "authInfo": {
            "authenticatedUsers": [{"user": "synthetic"}],
            "authenticatedUserPrivileges": [],
        }
    }
    verify_runtime_audit_permissions(client, "identity")
    assert "not enforcing retained audit protection" in caplog.text
