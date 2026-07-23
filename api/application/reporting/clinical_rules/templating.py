"""Restricted Jinja environment for clinical reporting rules."""

from __future__ import annotations

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment


def clinical_template_environment() -> SandboxedEnvironment:
    """Return the shared, deliberately small clinical template environment."""
    environment = SandboxedEnvironment(
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    environment.globals.clear()
    environment.filters = {
        name: environment.filters[name]
        for name in ("default", "join", "length", "lower", "round", "upper")
    }
    return environment
