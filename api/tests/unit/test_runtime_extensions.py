"""Optional deployment constraints receive only declared settings and fail closed."""

from types import SimpleNamespace

import pytest
from coyote_api.config import extensions


def test_validator_receives_only_declared_settings(monkeypatch):
    """Selected host values override environment fallbacks without leaking unrelated secrets."""
    seen = []

    class Validator:
        configuration_keys = ("SELECTED", "ENV_ONLY")

        def __call__(self, settings):
            seen.append(settings)

    monkeypatch.setenv("ENV_ONLY", "from-environment")
    monkeypatch.setenv("SELECTED", "ignored")
    monkeypatch.setattr(
        extensions, "entry_points", lambda **_: [SimpleNamespace(name="example", load=Validator)]
    )
    extensions.validate_runtime_extensions({"SELECTED": "resolved", "OTHER_SECRET": "private"})
    assert seen == [{"SELECTED": "resolved", "ENV_ONLY": "from-environment"}]


@pytest.mark.parametrize("keys", [None, ["SELECTED"], (42,)])
def test_invalid_key_declaration_prevents_initialization(monkeypatch, keys):
    validator = SimpleNamespace(configuration_keys=keys)
    monkeypatch.setattr(
        extensions,
        "entry_points",
        lambda **_: [SimpleNamespace(name="example", load=lambda: validator)],
    )
    with pytest.raises(RuntimeError, match="Deployment validation failed"):
        extensions.validate_runtime_extensions({})


def test_duplicate_validator_prevents_initialization(monkeypatch):
    def validator(_):
        pass

    validator.configuration_keys = ()
    entry = SimpleNamespace(name="example", load=lambda: validator)
    monkeypatch.setattr(extensions, "entry_points", lambda **_: [entry, entry])
    with pytest.raises(RuntimeError, match="Duplicate runtime validator"):
        extensions.validate_runtime_extensions({})


def test_disabled_demo_does_not_access_database(monkeypatch):
    """A normal deployment remains usable when the demo distribution is installed."""
    from coyote_demo.deployment import runtime_validator

    monkeypatch.setattr(
        extensions,
        "entry_points",
        lambda **_: [SimpleNamespace(name="demo", load=lambda: runtime_validator)],
    )
    extensions.validate_runtime_extensions({"COYOTE_DEMO_ENABLED": "0"})
