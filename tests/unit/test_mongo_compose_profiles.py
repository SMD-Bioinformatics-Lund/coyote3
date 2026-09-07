"""Offline Compose rendering: MongoDB must be opt-in, with independent storage."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def render(*profiles):
    if not shutil.which("docker"):
        pytest.skip("Docker Compose is required for offline profile rendering")
    command = [
        "docker",
        "compose",
        "--env-file",
        "deploy/env/example.env",
        "--env-file",
        "deploy/env/example.mongo-split.env",
        "-f",
        "deploy/compose/docker-compose.yml",
        "-f",
        "deploy/compose/docker-compose.mongo.yml",
    ]
    for profile in profiles:
        command.extend(["--profile", profile])
    result = subprocess.run(
        command + ["config", "--format", "json"],
        cwd=ROOT,
        env={**os.environ, "COYOTE3_VERSION": "4.0.0"},
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    "profiles,expected",
    [
        ((), set()),
        (("mongo",), {"mongo", "mongo_init"}),
        (("mongo-kb",), {"mongo-kb", "mongo_kb_init"}),
        (("mongo", "mongo-kb"), {"mongo", "mongo_init", "mongo-kb", "mongo_kb_init"}),
    ],
)
def test_mongo_services_are_selected_only_by_profile(profiles, expected):
    services = render(*profiles)["services"]
    assert {name for name in services if name.startswith("mongo")} == expected


def test_split_profile_has_independent_replica_sets_and_one_dbpath_per_instance():
    services = render("mongo", "mongo-kb")["services"]
    assert "coyote3-rs" in services["mongo"]["command"]
    assert "coyote3-kb-rs" in services["mongo-kb"]["command"]
    sources = []
    for name in ("mongo", "mongo-kb"):
        paths = [v for v in services[name]["volumes"] if v["target"] == "/data/db"]
        assert len(paths) == 1
        sources.append(paths[0]["source"])
    assert sources[0] != sources[1]
    for name in ("api", "worker", "beat"):
        env = services[name]["environment"]
        assert "mongo-app:27017" in env["COYOTE3_MONGO_URI"]
        assert "mongo-kb:27017" in env["KNOWLEDGEBASE_MONGO_URI"]
