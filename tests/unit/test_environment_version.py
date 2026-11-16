"""Verify environment labels are consistent across application versions."""

import pytest
from coyote_api.version import APPLICATION_VERSION, environment_version


@pytest.mark.parametrize(
    "environment,suffix",
    [
        ("production", ""),
        ("prod", ""),
        ("development", "-dev"),
        ("dev", "-dev"),
        ("testing", "-test"),
        ("test", "-test"),
        ("staging", "-stage"),
        ("stage", "-stage"),
    ],
)
def test_environment_version(environment, suffix):
    assert environment_version(environment) == APPLICATION_VERSION + suffix
