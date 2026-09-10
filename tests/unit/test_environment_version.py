"""Verify environment labels are consistent across application versions."""

import pytest

from api.version import __version__, environment_version


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
    assert environment_version(environment) == __version__ + suffix
