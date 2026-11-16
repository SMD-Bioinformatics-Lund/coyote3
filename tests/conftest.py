"""Pytest bootstrap for project-local imports."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
repo_root_str = str(REPO_ROOT)
if repo_root_str not in sys.path:
    sys.path.insert(0, repo_root_str)

# Keep test config deterministic regardless of caller shell environment.
os.environ.setdefault("COYOTE4_MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("COYOTE4_DB", "coyote4_test")
os.environ.setdefault("IDENTITY_DB", "coyote4_identity_test")
os.environ.setdefault("KNOWLEDGEBASE_DB", "coyote4_knowledgebase_test")
os.environ.setdefault("BAM_DB", "bam_test")

# Tests are a trusted host for direct application helpers as well as SDK operations.
from coyote.contracts.resource_integrity import using_resource_hasher  # noqa: E402
from coyote_mongo.resource_integrity import resource_content_hash  # noqa: E402


@pytest.fixture(autouse=True)
def application_resource_hasher():
    """Bind the deployed codec for application integration and tooling tests."""
    with using_resource_hasher(resource_content_hash):
        yield


def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    """Classify shared and package-owned suites by their repository-relative location."""
    for item in items:
        path = Path(item.fspath).resolve()
        if not path.is_relative_to(REPO_ROOT):
            continue
        relative = path.relative_to(REPO_ROOT).as_posix()
        if relative.startswith("tests/smoke/"):
            item.add_marker(pytest.mark.smoke)
            item.add_marker(pytest.mark.integration)
        elif relative.startswith("tests/unit/"):
            item.add_marker(pytest.mark.unit)
        elif relative.startswith("tests/integration/"):
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.contract)
