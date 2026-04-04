"""Architecture structure guardrails for the API package."""

from __future__ import annotations

from pathlib import Path


def test_canonical_api_packages_exist():
    """Test canonical api packages exist.

    Returns:
        The function result.
    """
    required_paths = [
        Path("api/main.py"),
        Path("api/config.py"),
        Path("api/lifecycle.py"),
        Path("api/routers"),
        Path("api/services"),
        Path("api/contracts"),
        Path("api/deps"),
        Path("api/infra/repositories"),
        Path("api/infra/db"),
        Path("api/infra/knowledgebase"),
        Path("api/infra/integrations"),
    ]

    missing = [path.as_posix() for path in required_paths if not path.exists()]
    assert not missing, "Missing canonical API architecture path(s):\n" + "\n".join(missing)
