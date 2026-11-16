"""Client suite selection without application or database imports."""

from pathlib import Path

import pytest


def pytest_collection_modifyitems(items):
    """Classify this distribution's tests, including the fast smoke subset."""
    directory = Path(__file__).parent
    for item in items:
        path = Path(item.path)
        if path.is_relative_to(directory):
            item.add_marker(pytest.mark.client)
            item.add_marker(pytest.mark.unit)
            if "smoke" in path.relative_to(directory).parts:
                item.add_marker(pytest.mark.smoke)
