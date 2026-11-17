# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Reject browser-test configurations that could reach or reuse clinical storage."""

from copy import deepcopy

import pytest

from deploy.installer.browser_tests import validate_stack
from deploy.installer.demo import load_settings, prepare


@pytest.fixture
def isolated_stack(tmp_path):
    """Use the demo's generated credentials and independently owned Compose resources."""
    prepare(tmp_path / "fresh", mode="docker", port=43111)
    record = load_settings(tmp_path / "fresh")
    project = record["compose"]["COYOTE_DEMO_PROJECT"]
    services = {
        name: {"networks": {"demo": {}}}
        for name in (
            "demo-mongo",
            "demo-replica",
            "demo-redis",
            "demo-storage",
            "demo-bootstrap",
            "api",
            "worker",
            "maintenance-worker",
            "beat",
            "frontend",
        )
    }
    for name in ("demo-storage", "demo-bootstrap", "api", "worker", "maintenance-worker", "beat"):
        services[name]["environment"] = deepcopy(record["environment"])
    services["frontend"]["networks"]["browser"] = {}
    services["frontend"]["ports"] = [{"host_ip": "127.0.0.1", "published": "43111", "target": 3000}]
    services["demo-mongo"]["volumes"] = [{"type": "volume", "source": "data", "target": "/data/db"}]
    return {
        "name": project,
        "services": services,
        "networks": {
            "demo": {"internal": True, "name": project + "_demo"},
            "browser": {"name": project + "_browser"},
        },
        "volumes": {"data": {"name": project + "_data"}},
    }


def validate(config):
    validate_stack(config, config["name"], 43111)


def test_new_demo_stack_is_accepted(isolated_stack):
    validate(isolated_stack)


@pytest.mark.parametrize(
    "service", ["api", "worker", "maintenance-worker", "beat", "demo-bootstrap"]
)
def test_every_database_writer_must_use_demo_storage(isolated_stack, service):
    isolated_stack["services"][service]["environment"]["COYOTE4_DB"] = "coyote4_production"
    with pytest.raises(ValueError):
        validate(isolated_stack)


@pytest.mark.parametrize(
    "uri",
    [
        "mongodb://user:secret@production.example.test:27017/",
        "mongodb://user:secret@127.0.0.1:28801/",
    ],
)
def test_remote_database_and_local_tunnel_are_both_rejected(isolated_stack, uri):
    isolated_stack["services"]["api"]["environment"]["COYOTE4_MONGO_URI"] = uri
    with pytest.raises(ValueError):
        validate(isolated_stack)


def test_existing_host_data_cannot_be_mounted(isolated_stack):
    isolated_stack["services"]["demo-mongo"]["volumes"][0].update(
        type="bind", source="/existing-data"
    )
    with pytest.raises(ValueError, match="mount host"):
        validate(isolated_stack)


def test_external_volume_cannot_be_selected(isolated_stack):
    isolated_stack["volumes"]["data"]["external"] = True
    with pytest.raises(ValueError, match="existing networks or volumes"):
        validate(isolated_stack)


def test_volume_with_another_projects_name_is_rejected(isolated_stack):
    isolated_stack["volumes"]["data"]["name"] = "ordinary_mongo"
    with pytest.raises(ValueError, match="existing networks or volumes"):
        validate(isolated_stack)


def test_database_cannot_publish_a_host_port(isolated_stack):
    isolated_stack["services"]["demo-mongo"]["ports"] = [{"published": "27017", "target": 27017}]
    with pytest.raises(ValueError, match="cannot publish"):
        validate(isolated_stack)


def test_frontend_cannot_be_exposed_to_the_network(isolated_stack):
    isolated_stack["services"]["frontend"]["ports"][0]["host_ip"] = "0.0.0.0"
    with pytest.raises(ValueError, match="loopback"):
        validate(isolated_stack)


def test_worker_cannot_join_the_host_network(isolated_stack):
    isolated_stack["services"]["worker"]["network_mode"] = "host"
    with pytest.raises(ValueError, match="host networks"):
        validate(isolated_stack)
