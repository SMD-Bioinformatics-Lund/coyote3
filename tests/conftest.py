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
os.environ.setdefault("COYOTE3_MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("COYOTE3_DB", "coyote3_test")
os.environ.setdefault("IDENTITY_DB", "coyote3_identity_test")
os.environ.setdefault("KNOWLEDGEBASE_DB", "coyote3_knowledgebase_test")
os.environ.setdefault("BAM_DB", "bam_test")

# Tests are a trusted host for direct application helpers as well as SDK operations.
from api.infra.mongo.resource_integrity import resource_content_hash  # noqa: E402
from coyote3.contracts.resource_integrity import configure_resource_hasher  # noqa: E402

configure_resource_hasher(resource_content_hash)


def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    """Apply suite markers by top-level tests directory."""
    for item in items:
        path = str(item.fspath)
        if "/tests/unit/" in path:
            item.add_marker(pytest.mark.unit)
        elif "/tests/api/" in path:
            item.add_marker(pytest.mark.api)
        elif "/tests/integration/" in path:
            item.add_marker(pytest.mark.contract)
