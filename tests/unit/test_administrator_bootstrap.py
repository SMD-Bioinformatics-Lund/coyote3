"""Administrator responsibility boundaries and initial credential restrictions."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.contracts.auth import ApiPasswordChangeRequest
from api.contracts.system import WhoamiPayload
from api.interfaces.http.operations.auth import change_password
from scripts.bootstrap_database import _make_bootstrap_user


def test_role_bundles_separate_clinical_and_system_responsibilities():
    path = Path("api/config/bootstrap/rbac/roles.seed.ndjson")
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
    with pytest.raises(HTTPException) as error:
        change_password(
            ApiPasswordChangeRequest(
                current_password="old",
                new_password="NewPassword!234",
                confirm_password=confirmation,
            ),
            user=SimpleNamespace(must_change_password=True),
        )
    assert error.value.status_code == 400
