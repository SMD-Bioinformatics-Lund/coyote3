"""Check first-installation identity transactions using disposable MongoDB databases."""

import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from pymongo import MongoClient
from pymongo.errors import BulkWriteError

from scripts.bootstrap_database import _initialize_governance, _make_bootstrap_user
from scripts.migrate_administrator_roles import migrate


@pytest.fixture
def bootstrap_database():
    uri = os.getenv("BOOTSTRAP_TEST_MONGO_URI")
    if not uri:
        pytest.skip("Set BOOTSTRAP_TEST_MONGO_URI for disposable bootstrap transactions")
    client = MongoClient(uri, serverSelectionTimeoutMS=3000)
    name = "coyote3_bootstrap_test_" + uuid4().hex
    try:
        yield client[name]
    finally:
        client.drop_database(name)
        client.close()


def initialize(database, *, duplicate_email=False):
    seed = {
        name: [
            json.loads(line)
            for line in Path(f"api/config/bootstrap/rbac/{name}.seed.ndjson")
            .read_text()
            .splitlines()
        ]
        for name in ("roles", "permissions")
    }
    accounts = [
        _make_bootstrap_user(
            argparse.Namespace(
                username=role,
                email=("shared" if duplicate_email else role) + "@example.test",
                password="Synthetic-Temporary-Password1!",
                role_id=role,
            ),
            actor="bootstrap",
        )
        for role in ("superuser", "sys_admin")
    ]
    return _initialize_governance(
        database,
        seed=seed,
        user_document=accounts[0],
        system_admin_document=accounts[1],
        users_collection="users",
        roles_collection="roles",
        permissions_collection="permissions",
    )


def test_initialization_installs_two_accounts_once(bootstrap_database):
    db = bootstrap_database
    assert initialize(db) == "loaded"
    hashes = {row["username"]: row["password"] for row in db.users.find()}
    assert len(hashes) == 2
    assert db.users.count_documents({"must_change_password": True, "system_managed": True}) == 2
    assert initialize(db) == "skipped"
    assert hashes == {row["username"]: row["password"] for row in db.users.find()}


def test_account_failure_rolls_back_all_governance(bootstrap_database):
    db = bootstrap_database
    with pytest.raises(BulkWriteError) as error:
        initialize(db, duplicate_email=True)
    assert error.value.details["writeErrors"][0]["code"] == 11000
    assert all(db[name].count_documents({}) == 0 for name in ("users", "roles", "permissions"))


def test_role_migration_requires_a_named_owner_and_is_repeatable(bootstrap_database):
    db = bootstrap_database
    db.users.insert_one({"username": "operator", "is_active": True, "roles": ["admin"]})
    db.roles.insert_one({"role_id": "admin", "permissions": ["app.controls:edit"]})
    with pytest.raises(ValueError):
        migrate(db, username="missing", apply=True)
    migrate(db, username="operator")
    assert db.users.find_one()["roles"] == ["admin"]
    migrate(db, username="operator", apply=True)
    migrate(db, username="operator", apply=True)
    assert db.users.find_one()["roles"] == ["admin", "sys_admin"]
    assert "app.controls:edit" not in db.roles.find_one({"role_id": "admin"})["permissions"]
