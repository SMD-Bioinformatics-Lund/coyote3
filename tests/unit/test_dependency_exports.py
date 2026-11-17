"""Dependency exports preserve shared development groups and reject invalid includes."""

import pytest

from scripts.quality.check_dependency_consistency import group_requirements, runtime_requirements


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


def test_runtime_exports_include_only_requested_local_features():
    projects = {
        "core": {
            "dependencies": ["pydantic==2.0"],
            "optional-dependencies": {
                "reporting": ["renderer==1.0"],
                "alignment": ["alignment-reader==1.0"],
                "test": ["pytest==9.0"],
            },
        },
        "server": {"dependencies": ["core[reporting]==1.0", "fastapi==1.0"]},
    }
    assert set(runtime_requirements(projects)) == {"pydantic==2.0", "renderer==1.0", "fastapi==1.0"}
    projects["server"]["dependencies"] = ["core[missing]==1.0"]
    with pytest.raises(ValueError, match="Unknown feature core"):
        runtime_requirements(projects)
