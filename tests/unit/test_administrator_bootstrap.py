"""Administrator responsibility boundaries and initial credential restrictions."""

import argparse
import json
from pathlib import Path

import pytest
from api_test_support import application_sdk as sdk_fixtures
from api_test_support import mock_collections as fx
from coyote.application.operations.account import Account
from coyote.contracts.auth import ApiPasswordChangeRequest
from coyote.domain.exceptions import AppError
from coyote_api.contracts.system import WhoamiPayload
from coyote_api.interfaces.http.v1.operations.auth import change_password

from scripts.bootstrap.bootstrap_database import _make_bootstrap_user


def test_bootstrap_cli_defaults_are_fixed_logins_with_generated_passwords(monkeypatch):
    """Fresh CLI installation requires no account prompts or configured default password."""
    from scripts.bootstrap import bootstrap_database

    monkeypatch.setattr("sys.argv", ["bootstrap", "--db", "synthetic", "--identity-db", "identity"])
    args = bootstrap_database.parse_args()
    assert args.superuser_username == "coyote4.superuser"
    assert args.system_admin_username == "coyote4.sysadmin"
    credentials = bootstrap_database._prepare_initial_credentials(args)
    assert len(credentials) == 2
    assert args.superuser_password != args.system_admin_password
    assert min(len(args.superuser_password), len(args.system_admin_password)) >= 16
    for username, email, password, role in (
        (args.superuser_username, args.superuser_email, args.superuser_password, "superuser"),
        (
            args.system_admin_username,
            args.system_admin_email,
            args.system_admin_password,
            "sys_admin",
        ),
    ):
        document = _make_bootstrap_user(
            argparse.Namespace(username=username, email=email, password=password, role_id=role),
            actor="system",
        )
        assert document["username"] == username
        assert document["must_change_password"] is True


def test_role_bundles_separate_clinical_and_system_responsibilities():
    path = Path("core/src/coyote/config/catalogs/rbac/roles.seed.ndjson")
    roles = {row["role_id"]: row for row in map(json.loads, path.read_text().splitlines())}
    clinical = set(roles["admin"]["permissions"])
    system = set(roles["sys_admin"]["permissions"])
    assert {"assay.panel:create", "clinical_rules:publish", "catalog:publish"} <= clinical
    assert not clinical & {"user:create", "user:role:edit", "role:edit", "app.controls:edit"}
    assert {"user:create", "user:role:edit", "role:edit", "app.controls:edit"} <= system
    assert not system & {
        "clinical_rules:publish",
        "catalog:publish",
        "assay.panel:edit",
        "snv:manage",
    }


@pytest.mark.parametrize("role", ["superuser", "sys_admin"])
def test_both_initial_accounts_are_protected_and_require_password_change(role):
    document = _make_bootstrap_user(
        argparse.Namespace(
            username="initial.operator",
            email="operator@example.test",
            role_id=role,
            password="Synthetic-Temporary-Password1!",
        ),
        actor="bootstrap",
    )
    assert document["must_change_password"] is True
    assert document["system_managed"] is True
    assert document["roles"] == [role]
    assert document["password"] != "Synthetic-Temporary-Password1!"


def test_whoami_preserves_the_password_change_flag():
    payload = WhoamiPayload(
        username="operator",
        roles=["sys_admin"],
        role="sys_admin",
        access_level=1000,
        permissions=[],
        ui_settings={},
        csrf_token="synthetic",
        must_change_password=True,
    )
    assert payload.model_dump()["must_change_password"] is True


@pytest.mark.parametrize("confirmation", [None, "different"])
def test_temporary_password_change_requires_matching_confirmation(confirmation):
    user = fx.api_user()
    user.must_change_password = True
    with pytest.raises(AppError) as error:
        change_password(
            ApiPasswordChangeRequest(
                current_password="old",
                new_password="NewPassword!234",
                confirm_password=confirmation,
            ),
            user=user,
            service=sdk_fixtures.authorized_operations(Account, None, user),
        )
    assert error.value.status_code == 400
