"""Classify Atlas-owned offline and optional host integration tests."""

from pathlib import Path

import pytest


def pytest_collection_modifyitems(items):
    """Mark tests without loading application configuration or contacting services."""
    directory = Path(__file__).parent
    for item in items:
        path = Path(item.path)
        if path.is_relative_to(directory):
            parts = path.relative_to(directory).parts
            item.add_marker(pytest.mark.integration if "api" in parts else pytest.mark.unit)
            if "smoke" in parts:
                item.add_marker(pytest.mark.smoke)
