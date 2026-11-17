"""Dependency exports preserve shared development groups and reject invalid includes."""

import pytest

from scripts.quality.check_dependency_consistency import group_requirements


def test_included_groups_supply_the_shared_version_to_each_consumer():
    groups = {
        "watch": ["watchdog[watchmedo]==7.1.0"],
        "dev": [{"include-group": "watch"}, "ruff==0.15.10"],
    }
    assert group_requirements(groups, "dev") == ["watchdog[watchmedo]==7.1.0", "ruff==0.15.10"]
    assert group_requirements(groups, "watch") == ["watchdog[watchmedo]==7.1.0"]


@pytest.mark.parametrize(
    "groups,message",
    [
        ({"dev": [{"include-group": "missing"}]}, "Unknown dependency group"),
        (
            {"dev": [{"include-group": "watch"}], "watch": [{"include-group": "dev"}]},
            "Cyclic dependency group",
        ),
        ({"dev": [{"unsupported": "watch"}]}, "Invalid dependency declaration"),
    ],
)
def test_invalid_groups_fail_before_accepting_an_export(groups, message):
    with pytest.raises(ValueError, match=message):
        group_requirements(groups, "dev")
